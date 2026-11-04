import logging
import secrets
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from app.database.mongodb import mongodb
from app.schemas.donation import DonationCreate, DonationUpdate
from fastapi import HTTPException
from app.services.workflow_service import log_audit

logger = logging.getLogger(__name__)

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
            {"id": donation_id}
        ]
    })

async def create_donation(donor_id: str, donation) -> dict:
    doc = donation.model_dump(by_alias=True) if hasattr(donation, "model_dump") else dict(donation)
    doc["donor_id"] = donor_id
    doc["donor_uid"] = donor_id
    
    # Retrieve donor name if available
    donor_user = await mongodb.db.users.find_one({
        "$or": [{"firebase_uid": donor_id}, {"id": donor_id}, {"email": donor_id}]
    })
    doc["donor_name"] = donor_user.get("name", "Vinay Aradhya") if donor_user else "Vinay Aradhya"
    
    now = datetime.now(timezone.utc)
    # Generate unique 4-digit code. In the Zomato delivery model:
    # Food Order ID is FB-XXXX and the exact 4 digits XXXX act as the handover OTP!
    order_num = secrets.randbelow(9000) + 1000
    food_order_id = f"FB-{order_num}"
    handover_otp = str(order_num)
    
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
    doc["_id"] = str(result.inserted_id)
    
    await log_audit("Donation", doc["id"], "DONATION_CREATED", donor_id, new_status=doc["status"])
    return doc

def _format_donation_response(doc: dict) -> dict:
    if not doc:
        return doc
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    elif "id" not in doc:
        doc["id"] = f"FB-{secrets.randbelow(9000) + 1000}"
        
    if not doc.get("food_order_id"):
        doc["food_order_id"] = doc.get("donation_id") or f"FB-{doc['id'][-4:].upper()}"
    if not doc.get("donation_id"):
        doc["donation_id"] = doc["food_order_id"]
    if not doc.get("donor_name") and doc.get("donor_id"):
        doc["donor_name"] = doc["donor_id"]

    # Extract 4-digit numeric code from food_order_id to unify order number & OTP (Zomato delivery model)
    digits = "".join(filter(str.isdigit, doc["food_order_id"]))
    if len(digits) >= 4:
        otp_val = digits[-4:]
    else:
        otp_val = str(secrets.randbelow(9000) + 1000)
        doc["food_order_id"] = f"FB-{otp_val}"
        doc["donation_id"] = doc["food_order_id"]

    doc["pickup_otp"] = doc.get("pickup_otp") or otp_val
    doc["delivery_otp"] = doc.get("delivery_otp") or otp_val
    doc["handover_otp"] = doc["delivery_otp"]
    return doc

async def get_donations(status: str = None, donor_id: str = None, skip: int = 0, limit: int = 100) -> list:
    query = {}
    if status and status.upper() != "ALL":
        query["status"] = {"$regex": f"^{status}$", "$options": "i"}
    if donor_id:
        query["$or"] = [{"donor_id": donor_id}, {"donor_uid": donor_id}]
    cursor = mongodb.db.donations.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_format_donation_response(doc) for doc in docs]

async def get_donations_by_donor(donor_id: str) -> list:
    query = {"$or": [{"donor_id": donor_id}, {"donor_uid": donor_id}]}
    cursor = mongodb.db.donations.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=1000)
    return [_format_donation_response(doc) for doc in docs]

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
    return [_format_donation_response(doc) for doc in docs]

async def get_ngo_history(ngo_id: str, skip: int = 0, limit: int = 100) -> list:
    query = {"$or": [{"matched_receiver": ngo_id}, {"accepted_by": ngo_id}, {"accepted_by_ngo_id": ngo_id}]}
    cursor = mongodb.db.donations.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_format_donation_response(doc) for doc in docs]

async def get_donation_by_id(donation_id: str) -> dict:
    doc = await _find_donation_doc(donation_id)
    return _format_donation_response(doc) if doc else None

import secrets
async def accept_donation(donation_id: str, ngo_id: str) -> dict:
    doc = await _find_donation_doc(donation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Donation not found")
        
    doc_id = doc["_id"]
    current_status = str(doc.get("status", "")).upper()
    if current_status not in ["AVAILABLE", "PENDING", "MATCHING"]:
        raise HTTPException(status_code=409, detail="Donation no longer available or already accepted")

    # Zomato Delivery Model: The last 4 digits of Food Order ID act as the handover OTP
    food_order_id = doc.get("food_order_id") or doc.get("donation_id") or ""
    digits = "".join(filter(str.isdigit, food_order_id))
    if len(digits) >= 4:
        handover_otp = digits[-4:]
    elif doc.get("pickup_otp"):
        handover_otp = str(doc.get("pickup_otp"))
    else:
        rand_num = secrets.randbelow(9000) + 1000
        handover_otp = str(rand_num)
        food_order_id = f"FB-{rand_num}"

    pickup_otp = handover_otp
    delivery_otp = handover_otp

    now = datetime.now(timezone.utc)

    result = await mongodb.db.donations.find_one_and_update(
        {"_id": doc_id, "status": doc.get("status")},
        {"$set": {
            "status": "MATCHED",
            "accepted_by": ngo_id,
            "matched_receiver": ngo_id,
            "accepted_by_ngo_id": ngo_id,
            "food_order_id": food_order_id,
            "pickup_otp": pickup_otp,
            "delivery_otp": delivery_otp,
            "handover_otp": delivery_otp,
            "otp_generated_at": now,
            "otp_expires_at": now + timedelta(hours=6),
            "updated_at": now
        }},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=409, detail="Donation no longer available or already accepted")
        
    result["id"] = str(result.pop("_id"))
    result["food_order_id"] = result.get("food_order_id") or food_order_id
    result["pickup_otp"] = pickup_otp
    result["delivery_otp"] = delivery_otp
    result["handover_otp"] = delivery_otp
    await log_audit("Donation", result["id"], "DONATION_ACCEPTED", ngo_id, old_status=current_status, new_status="MATCHED")
    return result

async def reject_donation(donation_id: str, ngo_id: str) -> dict:
    doc = await _find_donation_doc(donation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Donation not found")
    
    await mongodb.db.rejected_donations.insert_one({
        "donation_id": str(doc["_id"]),
        "ngo_id": ngo_id,
        "rejected_at": datetime.now(timezone.utc)
    })
    doc["id"] = str(doc.pop("_id"))
    return doc

async def update_donation(donation_id: str, donor_id: str, update_data: DonationUpdate) -> dict:
    doc = await _find_donation_doc(donation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Donation not found")
        
    is_admin = donor_id.startswith("admin") or donor_id == "mock_token_123"
    if not is_admin:
        caller = await mongodb.db.users.find_one({"$or": [{"firebase_uid": donor_id}, {"id": donor_id}]})
        if caller and str(caller.get("role", "")).lower() == "admin":
            is_admin = True
            
    if doc.get("donor_id") != donor_id and doc.get("donor_uid") != donor_id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    update_dict = update_data.model_dump(exclude_unset=True)
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    target_filter = {"_id": doc["_id"]}
    result = await mongodb.db.donations.find_one_and_update(
        target_filter,
        {"$set": update_dict},
        return_document=True
    )
    result["id"] = str(result.pop("_id"))
    await log_audit("Donation", result["id"], "DONATION_UPDATED", donor_id)
    return result

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
