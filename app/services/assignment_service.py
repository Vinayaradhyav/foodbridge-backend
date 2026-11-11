from datetime import datetime, timezone
from bson import ObjectId
from app.database.mongodb import get_database
from app.models.assignment import AssignmentModel
from app.schemas.assignment import AssignmentCreate
from app.services.workflow_service import WorkflowService, log_audit, get_donation_collection
from app.services.notification_service import create_notification
from app.schemas.notification import NotificationCreate
from fastapi import HTTPException

async def get_assignment_collection():
    db = get_database()
    return db.assignments

async def create_assignment(data: AssignmentCreate):
    collection = await get_assignment_collection()
    new_assignment = AssignmentModel.create_new_assignment(data.model_dump())

    # Synchronize assignment OTP and Food Order ID from parent donation so all roles see one unified OTP
    donation_col = await get_donation_collection()
    donation = None
    try:
        donation = await donation_col.find_one({"_id": ObjectId(data.donation_id)})
    except Exception:
        donation = await donation_col.find_one({"$or": [{"donation_id": data.donation_id}, {"food_order_id": data.donation_id}]})
    if donation:
        from app.services.donation_service import _derive_canonical_order_and_otp
        canonical_order, canonical_otp = _derive_canonical_order_and_otp(donation)
        new_assignment["food_order_id"] = canonical_order
        new_assignment["pickup_otp"] = canonical_otp
        new_assignment["delivery_otp"] = canonical_otp
        new_assignment["handover_otp"] = canonical_otp

    result = await collection.insert_one(new_assignment)
    
    # Sync Donation Status
    if donation:
        old_status = donation.get("status")
        await donation_col.update_one(
            {"_id": donation["_id"]},
            {"$set": {"status": "ASSIGNED", "assigned_volunteer_id": data.volunteer_id, "updated_at": datetime.now(timezone.utc)}}
        )
        await log_audit("Donation", str(donation["_id"]), "Assigned to Volunteer", "system", old_status, "ASSIGNED")
        
    created = await collection.find_one({"_id": result.inserted_id})
    
    await log_audit("Assignment", str(result.inserted_id), "Created Assignment", "system", None, "PENDING")
    
    # Notify Volunteer
    await create_notification(NotificationCreate(
        user_id=data.volunteer_id,
        title="New Assignment",
        message="You have been assigned a new pickup and delivery task.",
        type="VOLUNTEER_ASSIGNED",
        related_entity_id=str(result.inserted_id)
    ))
    
    return AssignmentModel.format_for_response(created)

async def get_assignment_by_id(assignment_id: str):
    collection = await get_assignment_collection()
    try:
        doc = await collection.find_one({"_id": ObjectId(assignment_id)})
        return AssignmentModel.format_for_response(doc)
    except Exception:
        return None

async def get_available_assignments(volunteer_id: str):
    collection = await get_assignment_collection()
    cursor = collection.find({
        "volunteer_id": volunteer_id,
        "status": "PENDING"
    }).sort("assigned_at", -1)
    assignments = await cursor.to_list(length=100)
    return [AssignmentModel.format_for_response(a) for a in assignments]

async def get_active_assignments():
    collection = await get_assignment_collection()
    cursor = collection.find({
        "status": {"$in": ["PENDING", "ACCEPTED", "PICKING_UP", "PICKED_UP", "IN_TRANSIT"]}
    }).sort("assigned_at", -1)
    assignments = await cursor.to_list(length=1000)
    return [AssignmentModel.format_for_response(a) for a in assignments]

async def get_volunteer_history(volunteer_id: str):
    collection = await get_assignment_collection()
    cursor = collection.find({
        "volunteer_id": volunteer_id,
        "status": {"$in": ["DELIVERED", "CANCELLED"]}
    }).sort("completed_at", -1)
    assignments = await cursor.to_list(length=100)
    return [AssignmentModel.format_for_response(a) for a in assignments]

async def update_assignment_status(assignment_id: str, volunteer_id: str, new_status: str):
    return await WorkflowService.transition_assignment(assignment_id, volunteer_id, new_status)
