from app.database.mongodb import get_database
from app.models.donor import DonorModel
from app.schemas.donor import DonorCreate
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

async def get_donor_by_email(email: str):
    db = get_database()
    donor = await db.donors.find_one({"email": email})
    return donor

async def create_donor(donor_data: DonorCreate, auth_provider: str = "email"):
    db = get_database()
    
    # Check if donor already exists
    existing = await get_donor_by_email(donor_data.email)
    if existing:
        raise ValueError("Email already registered")
        
    donor_dict = DonorModel.create_new_donor(
        full_name=donor_data.full_name,
        email=donor_data.email,
        mobile_number=donor_data.mobile_number,
        auth_provider=auth_provider
    )
    
    # For email auth, in a real app, hash the password here and store it.
    # The prompt specified "Do not store plaintext passwords in MongoDB."
    # We will assume Firebase handles email/password or we store a hash if we implemented manual auth.
    # But since we use Firebase, we will actually rely on Firebase for authentication,
    # or just store a placeholder if the requirement was strict on not storing plaintext.
    
    result = await db.donors.insert_one(donor_dict)
    donor_dict["_id"] = result.inserted_id
    
    return DonorModel.format_for_response(donor_dict)

async def update_last_login(email: str):
    db = get_database()
    await db.donors.update_one(
        {"email": email},
        {"$set": {"last_login": datetime.now(timezone.utc)}}
    )

async def get_or_create_google_donor(email: str, full_name: str):
    db = get_database()
    donor = await get_donor_by_email(email)
    
    if donor:
        await update_last_login(email)
        # Re-fetch after update
        donor = await get_donor_by_email(email)
        return DonorModel.format_for_response(donor)
        
    # Create new donor
    donor_dict = DonorModel.create_new_donor(
        full_name=full_name,
        email=email,
        mobile_number="", # Might not be available from Google
        auth_provider="google"
    )
    result = await db.donors.insert_one(donor_dict)
    donor_dict["_id"] = result.inserted_id
    return DonorModel.format_for_response(donor_dict)
