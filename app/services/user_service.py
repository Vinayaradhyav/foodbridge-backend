from datetime import datetime, timezone
import uuid
from app.database.mongodb import get_database
from app.models.user import UserModel
from app.schemas.user import UserCreate

async def get_user_collection():
    db = get_database()
    return db.users

async def get_user_by_email(email: str):
    collection = await get_user_collection()
    return await collection.find_one({"email": email})

async def get_user_by_firebase_uid(uid: str):
    collection = await get_user_collection()
    return await collection.find_one({"firebase_uid": uid})

from app.services.ai_verification_service import AIVerificationService
from app.core.security import hash_password

async def create_user(user_data: UserCreate):
    collection = await get_user_collection()
    
    is_receiver = (
        str(user_data.role).lower() in ["ngo", "receiver", "food_receiver", "relief_hub", "reliefhub"] or
        bool(user_data.receiver_type)
    )

    # Run AI Safety & Classification Screening
    ai_screening = {}
    if is_receiver:
        ai_screening = AIVerificationService.screen_organization(user_data.model_dump())

    # Separate accounts cleanly by role: Donor is Donor, Receiver is Receiver, Volunteer is Volunteer
    import re
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
        # Smoothly update account details and password ("user can register many time")
        update_fields = {
            "name": user_data.name,
            "location": user_data.location or existing_user.get("location", ""),
            "updated_at": datetime.now(timezone.utc),
            "status": "active" if not is_receiver else existing_user.get("status", "active")
        }
        if user_data.password:
            update_fields["hashed_password"] = hash_password(user_data.password)
        if user_data.phone:
            update_fields["phone"] = user_data.phone.strip()
        if user_data.email:
            update_fields["email"] = user_data.email.lower().strip()
        if user_data.receiver_type:
            update_fields["receiver_type"] = user_data.receiver_type
        if user_data.organization_id:
            update_fields["organization_id"] = user_data.organization_id
        if user_data.contact_person:
            update_fields["contact_person"] = user_data.contact_person
        if user_data.food_capacity is not None:
            update_fields["food_capacity"] = user_data.food_capacity
        if user_data.beneficiary_capacity is not None:
            update_fields["beneficiary_capacity"] = user_data.beneficiary_capacity
        if user_data.fleet_count is not None:
            update_fields["fleet_count"] = user_data.fleet_count
        if ai_screening:
            update_fields["ai_trust_score"] = ai_screening.get("ai_trust_score")
            update_fields["ai_safety_status"] = ai_screening.get("ai_safety_status")
            update_fields["ai_classification"] = ai_screening.get("ai_classification")
            update_fields["ai_notes"] = ai_screening.get("ai_notes")

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
    if is_receiver:
        new_user["status"] = "pending_approval"
        new_user["verification_status"] = "PENDING"
    else:
        new_user["status"] = "active"
        new_user["verification_status"] = "VERIFIED"

    if user_data.organization_id:
        new_user["organization_id"] = user_data.organization_id
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

    if ai_screening:
        new_user["ai_trust_score"] = ai_screening.get("ai_trust_score")
        new_user["ai_safety_status"] = ai_screening.get("ai_safety_status")
        new_user["ai_classification"] = ai_screening.get("ai_classification")
        new_user["ai_notes"] = ai_screening.get("ai_notes")

    result = await collection.insert_one(new_user)
    
    # Notify admin for any new registration (except admin itself)
    if user_data.role != "admin":
        db = get_database()
        await db.notifications.insert_one({
            "user_id": "admin",
            "title": "New Registration Pending Approval",
            "body": f"A new {user_data.role} ({user_data.name}) has registered. AI Trust Score: {ai_screening.get('ai_trust_score', 85)}%. Requires admin authorization.",
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
