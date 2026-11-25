from datetime import datetime, timezone
import uuid
import re
from app.database.mongodb import get_database
from app.models.user import UserModel
from app.schemas.user import UserCreate
from app.services.ai_verification_service import AIVerificationService
from app.services.government_verification_service import GovernmentVerificationService
from app.services.fraud_service import FraudService
from app.core.security import hash_password

async def get_user_collection():
    db = get_database()
    return db.users

async def get_user_by_email(email: str):
    collection = await get_user_collection()
    return await collection.find_one({"email": email})

async def get_user_by_firebase_uid(uid: str):
    collection = await get_user_collection()
    return await collection.find_one({"firebase_uid": uid})

async def create_user(user_data: UserCreate):
    collection = await get_user_collection()
    
    receiver_type = user_data.receiver_type
    is_individual_receiver = receiver_type == "NORMAL_INDIVIDUAL_RECEIVER"
    is_receiver = (
        str(user_data.role).lower() in ["ngo", "receiver", "food_receiver", "relief_hub", "reliefhub"] or
        bool(receiver_type)
    )

    # 1. Government ID & Darpan Validation
    darpan_raw = user_data.darpan_id or user_data.organization_id
    darpan_verif = {}
    if darpan_raw and darpan_raw.strip():
        # Validate format
        darpan_verif = GovernmentVerificationService.validate_darpan_id(darpan_raw)
        if not darpan_verif["is_valid"] and not is_individual_receiver:
            if receiver_type in ["NGO_TRUST", "FOOD_BANK"]:
                raise ValueError(darpan_verif["message"])

    # 2. AI Trust & Safety Fraud Assessment
    fraud_eval = await FraudService.evaluate_registration_fraud(user_data.model_dump())
    
    # 3. Organization Screening (only for formal NGOs/FoodBanks/Relief Hubs, NOT for individual families)
    ai_screening = {}
    if is_receiver and not is_individual_receiver:
        ai_screening = AIVerificationService.screen_organization(user_data.model_dump())
    elif is_individual_receiver:
        ai_screening = {
            "ai_trust_score": 95,
            "ai_safety_status": "SAFE - INDIVIDUAL BENEFICIARY",
            "ai_classification": "Direct Individual / Family Food Relief Recipient",
            "ai_notes": f"Individual food relief registration. Family size: {user_data.family_size or 1}. Dietary needs: {user_data.dietary_needs or 'General Meals'}.",
        }

    # Separate accounts cleanly by role
    r_lower = str(user_data.role).lower().strip()
    if is_receiver:
        role_filter = {"$in": ["ngo", "NGO", "receiver", "RECEIVER", "FOOD_RECEIVER", "food_receiver", "relief_hub", "RELIEF_HUB"]}
    elif r_lower == "volunteer":
        role_filter = {"$in": ["volunteer", "VOLUNTEER"]}
    else:
        role_filter = {"$in": ["donor", "DONOR"]}

    or_clauses = [{"email": user_data.email.lower().strip()}]
    if user_data.phone:
        clean_p = user_data.phone.strip()
        or_clauses.append({"phone": clean_p})
        p_digits = re.sub(r'\D', '', clean_p)
        if p_digits:
            or_clauses.append({"phone": p_digits})
            if len(p_digits) >= 10:
                or_clauses.append({"phone": p_digits[-10:]})
                or_clauses.append({"phone": f"+91{p_digits[-10:]}"})
                or_clauses.append({"phone": f"+91 {p_digits[-10:]}"})

    # Check if this user already exists for this exact role
    existing_user = await collection.find_one({"$and": [{"role": role_filter}, {"$or": or_clauses}]})
    if existing_user:
        # Smoothly update account details
        update_fields = {
            "name": user_data.name,
            "location": user_data.location or existing_user.get("location", ""),
            "updated_at": datetime.now(timezone.utc),
            "status": "active" if (not is_receiver or is_individual_receiver) else existing_user.get("status", "active")
        }
        if user_data.password:
            update_fields["hashed_password"] = hash_password(user_data.password)
        if user_data.phone:
            update_fields["phone"] = user_data.phone.strip()
        if user_data.email:
            update_fields["email"] = user_data.email.lower().strip()
        if user_data.receiver_type:
            update_fields["receiver_type"] = user_data.receiver_type
        if darpan_raw:
            update_fields["organization_id"] = darpan_raw.strip()
            update_fields["darpan_id"] = darpan_raw.strip()
        if darpan_verif:
            update_fields["darpan_verification_status"] = darpan_verif.get("status")
            update_fields["darpan_verification_method"] = darpan_verif.get("method")
        if user_data.contact_person:
            update_fields["contact_person"] = user_data.contact_person
        if user_data.food_capacity is not None:
            update_fields["food_capacity"] = user_data.food_capacity
        if user_data.beneficiary_capacity is not None:
            update_fields["beneficiary_capacity"] = user_data.beneficiary_capacity
        if user_data.fleet_count is not None:
            update_fields["fleet_count"] = user_data.fleet_count
        if user_data.family_size is not None:
            update_fields["family_size"] = user_data.family_size
        if user_data.dietary_needs:
            update_fields["dietary_needs"] = user_data.dietary_needs
        if ai_screening:
            update_fields["ai_trust_score"] = ai_screening.get("ai_trust_score")
            update_fields["ai_safety_status"] = ai_screening.get("ai_safety_status")
            update_fields["ai_classification"] = ai_screening.get("ai_classification")
            update_fields["ai_notes"] = ai_screening.get("ai_notes")
        if fraud_eval:
            update_fields["fraud_risk_score"] = fraud_eval.get("risk_score")
            update_fields["fraud_risk_level"] = fraud_eval.get("risk_level")
            update_fields["fraud_indicators"] = fraud_eval.get("indicators")

        await collection.update_one({"_id": existing_user["_id"]}, {"$set": update_fields})
        updated = await collection.find_one({"_id": existing_user["_id"]})
        return UserModel.format_for_response(updated)

    # Guard against unauthorized admin creation
    if str(user_data.role).strip().lower() == "admin":
        raise ValueError("Public registration for administrator accounts is not permitted.")

    assigned_uid = user_data.firebase_uid or f"uid_{uuid.uuid4().hex[:16]}"
    new_user = UserModel.create_new_user(
        firebase_uid=assigned_uid,
        name=user_data.name,
        email=user_data.email,
        phone=user_data.phone,
        role=user_data.role,
        location=user_data.location,
        receiver_type=user_data.receiver_type
    )
    
    # State assignment
    if is_individual_receiver:
        # Normal individuals are immediately active for receiving food portions
        new_user["status"] = "active"
        new_user["verification_status"] = "VERIFIED"
    elif is_receiver:
        new_user["status"] = "pending_approval"
        new_user["verification_status"] = "PENDING"
    else:
        new_user["status"] = "active"
        new_user["verification_status"] = "VERIFIED"

    if darpan_raw:
        new_user["organization_id"] = darpan_raw.strip()
        new_user["darpan_id"] = darpan_raw.strip()
    if darpan_verif:
        new_user["darpan_verification_status"] = darpan_verif.get("status")
        new_user["darpan_verification_method"] = darpan_verif.get("method")
        new_user["darpan_verified_at"] = datetime.now(timezone.utc)
    if user_data.contact_person:
        new_user["contact_person"] = user_data.contact_person
    if user_data.latitude is not None:
        new_user["latitude"] = user_data.latitude
    if user_data.longitude is not None:
        new_user["longitude"] = user_data.longitude
    if user_data.food_capacity is not None:
        new_user["food_capacity"] = user_data.food_capacity
    if user_data.beneficiary_capacity is not None:
        new_user["beneficiary_capacity"] = user_data.beneficiary_capacity
    if user_data.fleet_count is not None:
        new_user["fleet_count"] = user_data.fleet_count
    if user_data.vehicle_type:
        new_user["vehicle_type"] = user_data.vehicle_type
    if user_data.password:
        new_user["hashed_password"] = hash_password(user_data.password)

    # Individual receiver fields
    if user_data.family_size is not None:
        new_user["family_size"] = user_data.family_size
    if user_data.dietary_needs:
        new_user["dietary_needs"] = user_data.dietary_needs
    if user_data.id_proof_type:
        new_user["id_proof_type"] = user_data.id_proof_type
    if user_data.id_proof_number_masked:
        new_user["id_proof_number_masked"] = user_data.id_proof_number_masked

    # AI screening & Fraud metadata
    if ai_screening:
        new_user["ai_trust_score"] = ai_screening.get("ai_trust_score")
        new_user["ai_safety_status"] = ai_screening.get("ai_safety_status")
        new_user["ai_classification"] = ai_screening.get("ai_classification")
        new_user["ai_notes"] = ai_screening.get("ai_notes")

    if fraud_eval:
        new_user["fraud_risk_score"] = fraud_eval.get("risk_score")
        new_user["fraud_risk_level"] = fraud_eval.get("risk_level")
        new_user["fraud_indicators"] = fraud_eval.get("indicators")

    result = await collection.insert_one(new_user)
    
    # Notify admin for any new registration (except admin itself)
    if user_data.role != "admin":
        db = get_database()
        await db.notifications.insert_one({
            "user_id": "admin",
            "title": "New Registration Pending Approval" if is_receiver and not is_individual_receiver else "New Community Member Registered",
            "body": f"A new {user_data.role} ({user_data.name}) has registered. AI Trust Score: {ai_screening.get('ai_trust_score', 90)}%. Risk Level: {fraud_eval.get('risk_level', 'LOW_RISK')}.",
            "type": "ADMIN_ALERT",
            "read": False,
            "created_at": datetime.now(timezone.utc)
        })
        
    created_user = await collection.find_one({"_id": result.inserted_id})
    return UserModel.format_for_response(created_user)

async def update_last_login(firebase_uid: str):
    collection = await get_user_collection()
    await collection.update_one(
        {"firebase_uid": firebase_uid},
        {"$set": {"last_login": datetime.now(timezone.utc)}}
    )

async def update_user_profile(firebase_uid: str, profile_data: dict):
    collection = await get_user_collection()
    
    update_dict = {k: v for k, v in profile_data.items() if v is not None}
    if not update_dict:
        return await get_user_by_firebase_uid(firebase_uid)
        
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    await collection.update_one(
        {"firebase_uid": firebase_uid},
        {"$set": update_dict}
    )
    
    return await get_user_by_firebase_uid(firebase_uid)
