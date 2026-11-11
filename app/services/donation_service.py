import hashlib
import logging
import re
import secrets
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from app.database.mongodb import mongodb
from app.schemas.donation import DonationCreate, DonationUpdate
from fastapi import HTTPException
from app.services.workflow_service import log_audit
from app.services.notification_service import create_notification
from app.schemas.notification import NotificationCreate

logger = logging.getLogger(__name__)

_CLAIMABLE_STATUSES = {"AVAILABLE", "PENDING", "MATCHING", "CREATED", "NEW_DONATION", "UNDER_REVIEW"}
_ACTIVE_ACCEPTED_STATUSES = {"MATCHED", "ACCEPTED", "IN_TRANSIT", "ASSIGNED", "PICKUP_ASSIGNED", "PICKED_UP", "VOLUNTEER_ASSIGNED"}


async def _find_donation_doc(donation_id: str):
    try:
        doc = await mongodb.db.donations.find_one({"_id": ObjectId(donation_id)})
        if doc:
            return doc
    except Exception:
        pass
    return await mongodb.db.donations.find_one({
        "$or": [
            {"donation_id": donation_id},
            {"food_order_id": donation_id},
            {"id": donation_id},
        ]
    })


def _extract_four_digits(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(filter(str.isdigit, str(value)))
    return digits[-4:] if len(digits) >= 4 else None


def _derive_canonical_order_and_otp(doc: dict) -> tuple[str, str]:
    """
    Guarantees every donation has a canonical Zomato-style Order ID (`FB-XXXX`)
    whose last 4 numeric digits deterministically match `pickup_otp`,
    `delivery_otp`, and `handover_otp`.
    """
    raw_order = str(doc.get("food_order_id") or "").strip()
    if raw_order.upper().startswith(("FB-", "#FB-")):
        otp = _extract_four_digits(raw_order)
        if otp:
            return f"FB-{otp}", otp

    raw_don_id = str(doc.get("donation_id") or "").strip()
    if raw_don_id.upper().startswith(("FB-", "#FB-")):
        otp = _extract_four_digits(raw_don_id)
        if otp:
            return f"FB-{otp}", otp

    for field in ("handover_otp", "delivery_otp", "pickup_otp"):
        otp = _extract_four_digits(str(doc.get(field) or ""))
        if otp and len(str(doc.get(field) or "").strip()) == 4 and str(doc.get(field) or "").strip().isdigit():
            return f"FB-{otp}", str(doc.get(field)).strip()

    otp = _extract_four_digits(raw_don_id)
    if otp:
        return f"FB-{otp}", otp

    seed = str(doc.get("_id") or doc.get("id") or "foodbridge")
    digest_num = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    otp = str((digest_num % 9000) + 1000)
    return f"FB-{otp}", otp


async def _generate_unique_order_and_otp() -> tuple[str, str]:
    for _ in range(12):
        order_num = secrets.randbelow(9000) + 1000
        candidate_order = f"FB-{order_num}"
        existing = await mongodb.db.donations.find_one(
            {"food_order_id": candidate_order},
            {"_id": 1},
        )
        if not existing:
            return candidate_order, str(order_num)
    fallback_num = secrets.randbelow(9000) + 1000
    return f"FB-{fallback_num}", str(fallback_num)


async def _enrich_donation_names(docs: list[dict]) -> list[dict]:
    if not docs:
        return docs
    uids: set[str] = set()
    for d in docs:
        if d.get("donor_id"):
            uids.add(str(d["donor_id"]))
        acc = d.get("accepted_by") or d.get("accepted_by_ngo_id") or d.get("matched_receiver")
        if acc:
            uids.add(str(acc))
    if not uids:
        return [_format_donation_response(d) for d in docs]

    uid_list = list(uids)
    cursor = mongodb.db.users.find(
        {"$or": [{"firebase_uid": {"$in": uid_list}}, {"id": {"$in": uid_list}}]},
        {"firebase_uid": 1, "id": 1, "name": 1},
    )
    name_map: dict[str, str] = {}
    async for u in cursor:
        uname = u.get("name")
        if not uname:
            continue
        if u.get("firebase_uid"):
            name_map[str(u["firebase_uid"])] = str(uname)
        if u.get("id"):
            name_map[str(u["id"])] = str(uname)

    enriched = []
    for d in docs:
        did = str(d.get("donor_id") or "")
        if did in name_map and (not d.get("donor_name") or d.get("donor_name") == did):
            d["donor_name"] = name_map[did]
        acc = d.get("accepted_by") or d.get("accepted_by_ngo_id") or d.get("matched_receiver")
        if acc and not d.get("accepted_by_name"):
            acc_str = str(acc)
            d["accepted_by_name"] = name_map.get(acc_str, acc_str if not acc_str.startswith("user_") else "Relief Partner")
        enriched.append(_format_donation_response(d))
    return enriched


async def create_donation(donor_id: str, donation) -> dict:
    doc = donation.model_dump(by_alias=True) if hasattr(donation, "model_dump") else dict(donation)
    doc["donor_id"] = donor_id
    doc["donor_uid"] = donor_id

    now = datetime.now(timezone.utc)

    # 1. Exact idempotency check if client supplied an idempotency_key
    idem_key = (doc.get("idempotency_key") or "").strip()
    if idem_key:
        existing = await mongodb.db.donations.find_one({
            "donor_id": donor_id,
            "idempotency_key": idem_key,
        })
        if existing:
            logger.info(f"[Idempotency] Returning existing donation for key={idem_key}")
            res = await _enrich_donation_names([existing])
            return res[0]

    # 2. Temporal deduplication window (180s) for double-taps or dual client submits
    norm_food = re.sub(r"\s+", " ", str(doc.get("food_name") or "").strip()).lower()
    norm_loc = re.sub(r"\s+", " ", str(doc.get("pickup_location") or "").strip()).lower()
    try:
        qty_val = float(doc.get("quantity") or 0)
    except Exception:
        qty_val = 0.0
    cutoff = now - timedelta(seconds=180)
    recent_cursor = mongodb.db.donations.find({
        "$or": [{"donor_id": donor_id}, {"donor_uid": donor_id}],
        "created_at": {"$gte": cutoff},
        "status": {"$nin": ["CANCELLED", "EXPIRED", "REJECTED"]},
    }).sort("created_at", -1).limit(10)
    async for cand in recent_cursor:
        c_food = re.sub(r"\s+", " ", str(cand.get("food_name") or "").strip()).lower()
        c_loc = re.sub(r"\s+", " ", str(cand.get("pickup_location") or "").strip()).lower()
        try:
            c_qty = float(cand.get("quantity") or 0)
        except Exception:
            c_qty = 0.0
        if c_food == norm_food and c_loc == norm_loc and abs(c_qty - qty_val) < 0.01:
            logger.info(f"[Dedup] Suppressing duplicate donation within 180s for donor={donor_id}, food={norm_food}")
            res = await _enrich_donation_names([cand])
            return res[0]

    # Retrieve donor name if available
    donor_user = await mongodb.db.users.find_one({
        "$or": [{"firebase_uid": donor_id}, {"id": donor_id}, {"email": donor_id}]
    })
    doc["donor_name"] = donor_user.get("name", "Food Donor") if donor_user else "Food Donor"

    # Normalize number_of_meals so it is never 0 when quantity > 0
    if not doc.get("number_of_meals") or int(doc.get("number_of_meals") or 0) <= 0:
        if qty_val > 0:
            doc["number_of_meals"] = max(1, int(round(qty_val)))

    # Generate unique 4-digit code (Zomato delivery model: FB-XXXX & OTP XXXX)
    food_order_id, handover_otp = await _generate_unique_order_and_otp()

    doc["food_order_id"] = food_order_id
    doc["donation_id"] = food_order_id
    doc["pickup_otp"] = handover_otp
    doc["delivery_otp"] = handover_otp
    doc["handover_otp"] = handover_otp
    doc["status"] = doc.get("status") or "AVAILABLE"
    doc["created_at"] = now
    doc["updated_at"] = now

    result = await mongodb.db.donations.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc["_id"] = result.inserted_id

    await log_audit("Donation", doc["id"], "DONATION_CREATED", donor_id, new_status=doc["status"])
    return _format_donation_response(doc)


def _format_donation_response(doc: dict) -> dict:
    if not doc:
        return doc
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    elif "id" not in doc:
        doc["id"] = f"FB-{secrets.randbelow(9000) + 1000}"

    if not doc.get("donor_name") and doc.get("donor_id"):
        doc["donor_name"] = doc["donor_id"]

    canonical_order, canonical_otp = _derive_canonical_order_and_otp(doc)
    doc["food_order_id"] = canonical_order
    doc["donation_id"] = canonical_order
    doc["pickup_otp"] = canonical_otp
    doc["delivery_otp"] = canonical_otp
    doc["handover_otp"] = canonical_otp

    # Normalize meals count cleanly
    try:
        meals = int(doc.get("number_of_meals") or 0)
    except Exception:
        meals = 0
    if meals <= 0:
        try:
            qty = float(doc.get("quantity") or 0)
            if qty > 0:
                meals = max(1, int(round(qty)))
        except Exception:
            meals = 0
    doc["number_of_meals"] = meals
    doc["food_image"] = doc.get("food_image") or ""
    return doc

async def get_donations(status: str = None, donor_id: str = None, skip: int = 0, limit: int = 100) -> list:
    query = {}
    if status and status.upper() != "ALL":
        query["status"] = {"$regex": f"^{status}$", "$options": "i"}
    if donor_id:
        query["$or"] = [{"donor_id": donor_id}, {"donor_uid": donor_id}]
    cursor = mongodb.db.donations.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return await _enrich_donation_names(docs)

async def get_donations_by_donor(donor_id: str) -> list:
    query = {"$or": [{"donor_id": donor_id}, {"donor_uid": donor_id}]}
    cursor = mongodb.db.donations.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=1000)
    return await _enrich_donation_names(docs)

async def get_available_for_ngo(ngo_id: str, skip: int = 0, limit: int = 100) -> list:
    # Filter out donations that this NGO has rejected
    rejected = await mongodb.db.rejected_donations.find({"ngo_id": ngo_id}).to_list(length=1000)
    rejected_ids = []
    for r in rejected:
        try:
            rejected_ids.append(ObjectId(r["donation_id"]))
        except Exception:
            pass
    
    query = {"status": {"$in": ["AVAILABLE", "PENDING", "MATCHING"]}, "_id": {"$nin": rejected_ids}}
    cursor = mongodb.db.donations.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return await _enrich_donation_names(docs)

async def get_ngo_history(ngo_id: str, skip: int = 0, limit: int = 100) -> list:
    query = {"$or": [{"matched_receiver": ngo_id}, {"accepted_by": ngo_id}, {"accepted_by_ngo_id": ngo_id}]}
    cursor = mongodb.db.donations.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return await _enrich_donation_names(docs)

async def get_donation_by_id(donation_id: str) -> dict:
    doc = await _find_donation_doc(donation_id)
    if not doc:
        return None
    res = await _enrich_donation_names([doc])
    return res[0]

async def accept_donation(
    donation_id: str,
    ngo_id: str,
    volunteer_name: str = None,
    target_status: str = None,
    ngo_name: str = None,
) -> dict:
    doc = await _find_donation_doc(donation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Donation not found")

    doc_id = doc["_id"]
    current_status = str(doc.get("status", "")).upper()

    resolved_ngo_name = (ngo_name or "").strip()
    if not resolved_ngo_name:
        ngo_user = await mongodb.db.users.find_one(
            {"$or": [{"firebase_uid": ngo_id}, {"id": ngo_id}, {"email": ngo_id}]},
            {"name": 1},
        )
        resolved_ngo_name = (ngo_user.get("name") if ngo_user else None) or ngo_id

    desired_status = (target_status or "MATCHED").upper()
    if desired_status not in {"MATCHED", "ACCEPTED", "IN_TRANSIT"}:
        desired_status = "MATCHED"

    # Idempotent retry guard: if ALREADY accepted by THIS SAME receiver mid-flow,
    # safely enrich/sync without creating duplicates or raising a spurious 409.
    existing_accepters = {
        str(x).strip()
        for x in (doc.get("accepted_by"), doc.get("accepted_by_ngo_id"), doc.get("matched_receiver"))
        if x
    }
    if current_status in _ACTIVE_ACCEPTED_STATUSES:
        if ngo_id in existing_accepters:
            update_retry = {"updated_at": datetime.now(timezone.utc)}
            if desired_status == "IN_TRANSIT" and current_status in {"MATCHED", "ACCEPTED"}:
                update_retry["status"] = "IN_TRANSIT"
            if volunteer_name and not doc.get("volunteer_name"):
                update_retry["volunteer_name"] = volunteer_name
            if not doc.get("accepted_by_name") and resolved_ngo_name:
                update_retry["accepted_by_name"] = resolved_ngo_name
            canonical_order, canonical_otp = _derive_canonical_order_and_otp(doc)
            update_retry.update({
                "food_order_id": canonical_order,
                "donation_id": canonical_order,
                "pickup_otp": canonical_otp,
                "delivery_otp": canonical_otp,
                "handover_otp": canonical_otp,
            })
            updated = await mongodb.db.donations.find_one_and_update(
                {"_id": doc_id},
                {"$set": update_retry},
                return_document=True,
            )
            res = await _enrich_donation_names([updated or doc])
            return res[0]
        raise HTTPException(status_code=409, detail="Donation already accepted by another receiver")

    if current_status not in _CLAIMABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Donation no longer available or already accepted")

    # Canonical Zomato Delivery Model: Order ID FB-XXXX & unified 4-digit OTP XXXX
    food_order_id, handover_otp = _derive_canonical_order_and_otp(doc)
    now = datetime.now(timezone.utc)

    update_fields = {
        "status": desired_status,
        "accepted_by": ngo_id,
        "accepted_by_name": resolved_ngo_name,
        "matched_receiver": ngo_id,
        "accepted_by_ngo_id": ngo_id,
        "food_order_id": food_order_id,
        "donation_id": food_order_id,
        "pickup_otp": handover_otp,
        "delivery_otp": handover_otp,
        "handover_otp": handover_otp,
        "accepted_at": now,
        "otp_generated_at": now,
        "otp_expires_at": now + timedelta(hours=6),
        "updated_at": now,
    }
    if volunteer_name:
        update_fields["volunteer_name"] = volunteer_name

    result = await mongodb.db.donations.find_one_and_update(
        {"_id": doc_id, "status": doc.get("status")},
        {"$set": update_fields},
        return_document=True,
    )
    if not result:
        latest = await mongodb.db.donations.find_one({"_id": doc_id})
        if latest and ngo_id in {latest.get("accepted_by"), latest.get("matched_receiver"), latest.get("accepted_by_ngo_id")}:
            res = await _enrich_donation_names([latest])
            return res[0]
        raise HTTPException(status_code=409, detail="Donation no longer available or already accepted")

    await log_audit("Donation", str(doc_id), "DONATION_ACCEPTED", ngo_id, old_status=current_status, new_status=desired_status)

    if result.get("donor_id"):
        try:
            await create_notification(NotificationCreate(
                user_id=str(result["donor_id"]),
                title=f"Donation Claimed (#{food_order_id})",
                message=f"{resolved_ngo_name} claimed your {result.get('food_name', 'food')} donation. Handover OTP: {handover_otp}.",
                type="DONATION_ACCEPTED",
                related_entity_id=str(doc_id),
            ))
        except Exception as n_err:
            logger.warning(f"Donor claim notification skipped: {n_err}")

    res = await _enrich_donation_names([result])
    return res[0]

async def reject_donation(donation_id: str, ngo_id: str) -> dict:
    doc = await _find_donation_doc(donation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Donation not found")
    
    await mongodb.db.rejected_donations.insert_one({
        "donation_id": str(doc["_id"]),
        "ngo_id": ngo_id,
        "rejected_at": datetime.now(timezone.utc)
    })
    res = await _enrich_donation_names([doc])
    return res[0]

async def update_donation(donation_id: str, donor_id: str, update_data: DonationUpdate) -> dict:
    doc = await _find_donation_doc(donation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Donation not found")
        
    is_admin = donor_id.startswith("admin") or donor_id == "mock_token_123"
    if not is_admin:
        caller = await mongodb.db.users.find_one({"$or": [{"firebase_uid": donor_id}, {"id": donor_id}]})
        if caller and str(caller.get("role", "")).lower() == "admin":
            is_admin = True
            
    if doc.get("donor_id") != donor_id and doc.get("donor_uid") != donor_id and doc.get("accepted_by") != donor_id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    update_dict = update_data.model_dump(exclude_unset=True)
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    target_filter = {"_id": doc["_id"]}
    result = await mongodb.db.donations.find_one_and_update(
        target_filter,
        {"$set": update_dict},
        return_document=True
    )
    await log_audit("Donation", str(doc["_id"]), "DONATION_UPDATED", donor_id)
    res = await _enrich_donation_names([result])
    return res[0]

async def delete_donation(donation_id: str, donor_id: str):
    doc = await _find_donation_doc(donation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Donation not found")
    is_admin = donor_id.startswith("admin") or donor_id == "mock_token_123"
    if not is_admin and doc.get("donor_id") != donor_id and doc.get("donor_uid") != donor_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    await mongodb.db.donations.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "CANCELLED", "updated_at": datetime.now(timezone.utc)}}
    )
    await log_audit("Donation", str(doc["_id"]), "DONATION_DELETED", donor_id, old_status=doc.get("status"), new_status="CANCELLED")

class DonationService:
    # Retain the legacy method for matching engine
    async def get_active_donations(self, limit: int = 50) -> list:
        terminal_states = ["COMPLETED", "REJECTED", "CANCELLED", "EXPIRED", "FOOD_REJECTED"]
        cursor = mongodb.db.donations.find({"status": {"$nin": terminal_states}}).sort("created_at", -1).limit(limit)
        donations = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            donations.append(doc)
        return donations
        
donation_service = DonationService()
