from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr
from app.schemas.user import (
    UserCreate, UserResponse, LoginRequest, NgoProfileUpdate, 
    VolunteerProfileUpdate, VolunteerAvailabilityUpdate, FcmTokenUpdate,
    ForgotPasswordRequest, ResetPasswordRequest, SendVerificationEmailRequest, VerifyEmailRequest
)
from app.services.user_service import (
    create_user, get_user_by_firebase_uid, update_last_login, 
    update_user_profile, get_user_collection, get_user_by_email
)
from app.models.user import UserModel
from app.core.security import (
    get_current_user, create_access_token, hash_password, 
    verify_password, revoke_token, security
)
import hashlib
import os
import random
from datetime import datetime, timezone, timedelta

class AdminRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str
    role: str = "admin"

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

class AdminForgotRequest(BaseModel):
    email: EmailStr

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    if user.role.strip().lower() == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration for administrator accounts is not permitted. Administrator accounts must be provisioned through authorized system administration."
        )
    try:
        new_user = await create_user(user)
        # Generate real JWT token
        token = create_access_token({"sub": new_user.get("firebase_uid", str(new_user.get("_id", ""))), "role": new_user.get("role")})
        new_user["access_token"] = token
        new_user["token_type"] = "bearer"
        return new_user
    except ValueError as e:
        err_msg = str(e)
        status_code = status.HTTP_409_CONFLICT if "already registered" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=err_msg
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to create your account: {str(e)}"
        )

@router.post("/login", response_model=UserResponse)
async def login(credentials: LoginRequest):
    try:
        from app.database.mongodb import get_database
        db = get_database()
        
        search_terms = []
        if credentials.firebase_uid:
            search_terms.append({"firebase_uid": credentials.firebase_uid})
        if credentials.email:
            e_str = str(credentials.email).lower().strip()
            search_terms.append({"email": e_str})
            import re
            e_digits = re.sub(r'\D', '', e_str)
            if len(e_digits) >= 10:
                search_terms.append({"phone": e_digits})
                search_terms.append({"phone": f"+91{e_digits}"})
                search_terms.append({"phone": f"+91 {e_digits}"})
        if credentials.phone:
            clean_p = credentials.phone.strip()
            search_terms.append({"phone": clean_p})
            search_terms.append({"email": clean_p.lower()})
            import re
            digits = re.sub(r'\D', '', clean_p)
            if digits:
                last10 = digits[-10:] if len(digits) >= 10 else digits
                search_terms.append({"phone": digits})
                search_terms.append({"phone": last10})
                search_terms.append({"phone": f"+91{last10}"})
                search_terms.append({"phone": f"+91 {last10}"})
                search_terms.append({"phone": {"$regex": f"{last10}$"}})

        if not search_terms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide an email or phone number to sign in."
            )

        # Determine role filter when role is passed: Donor only uses Donor, Receiver uses Receiver, Volunteer uses Volunteer
        allowed_roles = None
        if credentials.role:
            r_req = str(credentials.role).strip().lower()
            if r_req == "donor":
                allowed_roles = ["donor", "DONOR"]
            elif r_req in ["receiver", "ngo", "food_receiver", "relief_hub", "reliefhub"]:
                allowed_roles = ["ngo", "NGO", "receiver", "RECEIVER", "FOOD_RECEIVER", "food_receiver", "relief_hub", "RELIEF_HUB"]
            elif r_req == "volunteer":
                allowed_roles = ["volunteer", "VOLUNTEER"]
            elif r_req == "admin":
                allowed_roles = ["admin", "ADMIN"]

        user = None
        if allowed_roles:
            user = await db.users.find_one({"$and": [{"role": {"$in": allowed_roles}}, {"$or": search_terms}]})
        
        if not user:
            # Check if user exists under a DIFFERENT role to give a clear explanation
            other_user = await db.users.find_one({"$or": search_terms})
            if other_user and allowed_roles:
                actual_role = str(other_user.get("role", "another role")).upper()
                req_title = "Donor" if "donor" in allowed_roles else ("Receiver" if "ngo" in allowed_roles else "Volunteer")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"This account is registered as a {actual_role}. Please sign in via the appropriate portal or register as a {req_title}."
                )
            if not allowed_roles and other_user:
                user = other_user
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Account not found. Please register or verify your phone/email."
                )

        if user.get("status") == "deleted":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been permanently deleted."
            )

        if user.get("status") in ("rejected", "suspended") or user.get("verification_status") in ("REJECTED", "SUSPENDED"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account application has been rejected by administration. Please contact support."
            )

        # Verify password if user has hashed_password and credentials.password is given
        if credentials.password and user.get("hashed_password"):
            pw = credentials.password.strip()
            hp = user.get("hashed_password")
            if not (verify_password(pw, hp) or 
                    verify_password(pw.lower(), hp) or 
                    verify_password(pw.capitalize(), hp) or
                    verify_password(pw.upper(), hp)):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid password. Please check your credentials."
                )

        uid = user.get("firebase_uid", credentials.firebase_uid or str(user.get("_id")))
        await update_last_login(uid)
        refreshed = await db.users.find_one({"_id": user["_id"]})
        formatted = UserModel.format_for_response(refreshed or user)
        
        # Issue real JWT Token
        token = create_access_token({"sub": uid, "role": formatted.get("role", "donor")})
        formatted["access_token"] = token
        formatted["token_type"] = "bearer"
        return formatted
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/logout")
async def logout(request: Request):
    """Real logout endpoint that invalidates the caller's JWT token."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        revoke_token(token)
    return {"status": "success", "message": "Successfully logged out of Food-Bridge session."}

# ==================== PASSWORD RESET (Item 2) ====================
@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Generate and record a 6-digit password reset OTP with 15-minute expiry."""
    from app.database.mongodb import get_database
    db = get_database()
    email_clean = str(req.email).lower().strip()
    user = await db.users.find_one({"email": email_clean})
    if not user:
        # Prevent account enumeration: return consistent response
        return {"status": "success", "message": f"If an account is associated with {email_clean}, a reset code has been sent."}

    # Generate 6-digit numeric OTP
    otp = str(random.randint(100000, 999999))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    await db.password_resets.update_one(
        {"email": email_clean},
        {"$set": {
            "email": email_clean,
            "otp": otp,
            "expires_at": expires_at,
            "used": False,
            "created_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

    # In production, dispatch via SMTP/SendGrid. For testing/dev, log to console & include in response
    print(f"[SECURITY OTP] Password reset OTP for {email_clean}: {otp}")
    return {
        "status": "success", 
        "message": f"Reset code sent to {email_clean}. Code expires in 15 minutes.",
        "dev_otp": otp  # Accessible in dev for seamless instant testing
    }

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Verify reset OTP and update password."""
    from app.database.mongodb import get_database
    db = get_database()
    email_clean = str(req.email).lower().strip()
    
    reset_entry = await db.password_resets.find_one({"email": email_clean, "used": False})
    if not reset_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active password reset request found for this email. Please request a new code."
        )

    if datetime.now(timezone.utc) > reset_entry["expires_at"].replace(tzinfo=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset code has expired. Please request a new one."
        )

    if reset_entry["otp"].strip() != req.otp.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset code. Please double-check the 6-digit code."
        )

    # Hash new password
    hashed = hash_password(req.new_password)
    now = datetime.now(timezone.utc)

    # Update user
    update_res = await db.users.update_one(
        {"email": email_clean},
        {"$set": {
            "hashed_password": hashed,
            "updated_at": now
        }}
    )

    # Mark reset token as used
    await db.password_resets.update_one({"_id": reset_entry["_id"]}, {"$set": {"used": True}})

    return {"status": "success", "message": "Password updated successfully. You can now log in with your new credentials."}

# ==================== EMAIL VERIFICATION (Item 3) ====================
@router.post("/send-verification-email")
async def send_verification_email(req: SendVerificationEmailRequest):
    """Generate and dispatch email verification code."""
    from app.database.mongodb import get_database
    db = get_database()
    email_clean = str(req.email).lower().strip()
    user = await db.users.find_one({"email": email_clean})
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    code = str(random.randint(100000, 999999))
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    await db.email_verifications.update_one(
        {"email": email_clean},
        {"$set": {
            "email": email_clean,
            "code": code,
            "expires_at": expires_at,
            "verified": False,
            "created_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

    print(f"[SECURITY] Email verification code for {email_clean}: {code}")
    return {
        "status": "success",
        "message": f"Verification code sent to {email_clean}.",
        "dev_code": code
    }

@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest):
    """Verify email with code."""
    from app.database.mongodb import get_database
    db = get_database()
    email_clean = str(req.email).lower().strip()

    record = await db.email_verifications.find_one({"email": email_clean, "verified": False})
    if not record:
        raise HTTPException(status_code=400, detail="No pending verification found for this email.")

    if record["code"].strip() != req.code.strip():
        raise HTTPException(status_code=400, detail="Invalid verification code.")

    # Mark user as verified
    await db.users.update_one(
        {"email": email_clean},
        {"$set": {
            "is_email_verified": True,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    await db.email_verifications.update_one({"_id": record["_id"]}, {"$set": {"verified": True}})

    return {"status": "success", "message": "Email verified successfully!"}

# ==================== ADMIN AUTH ====================
@router.get("/admin/exists")
async def check_admin_exists():
    collection = await get_user_collection()
    existing_admin = await collection.find_one({"role": "admin"})
    return {"exists": existing_admin is not None}

@router.post("/admin/register", response_model=UserResponse)
async def admin_register(req: AdminRegisterRequest):
    collection = await get_user_collection()
    existing_email = await get_user_by_email(req.email)
    if existing_email:
        hashed = hash_password(req.password)
        await collection.update_one(
            {"_id": existing_email["_id"]},
            {"$set": {
                "name": req.name,
                "phone": req.phone,
                "role": "admin",
                "hashed_password": hashed,
                "status": "active",
                "verification_status": "VERIFIED",
                "is_email_verified": True,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        updated = await collection.find_one({"_id": existing_email["_id"]})
        formatted = UserModel.format_for_response(updated)
        token = create_access_token({"sub": formatted["firebase_uid"], "role": "admin"})
        formatted["access_token"] = token
        formatted["token_type"] = "bearer"
        return formatted
        
    firebase_uid = f"admin_{os.urandom(8).hex()}"
    new_user = UserModel.create_new_user(
        firebase_uid=firebase_uid,
        name=req.name,
        email=req.email,
        phone=req.phone,
        role="admin",
        location=""
    )
    new_user["status"] = "active"
    new_user["verification_status"] = "VERIFIED"
    new_user["is_email_verified"] = True
    new_user["hashed_password"] = hash_password(req.password)
    
    result = await collection.insert_one(new_user)
    created_user = await collection.find_one({"_id": result.inserted_id})
    formatted = UserModel.format_for_response(created_user)
    token = create_access_token({"sub": formatted["firebase_uid"], "role": "admin"})
    formatted["access_token"] = token
    formatted["token_type"] = "bearer"
    return formatted

@router.post("/admin/login", response_model=UserResponse)
async def admin_login(req: AdminLoginRequest):
    collection = await get_user_collection()
    user = await collection.find_one({"email": req.email, "role": "admin"})
    if not user:
        raise HTTPException(status_code=404, detail="Admin account not found.")
        
    hashed = user.get("hashed_password")
    if not hashed or not verify_password(req.password, hashed):
        raise HTTPException(status_code=401, detail="Invalid admin credentials.")
        
    await update_last_login(user["firebase_uid"])
    user = await get_user_by_firebase_uid(user["firebase_uid"])
    formatted = UserModel.format_for_response(user)
    token = create_access_token({"sub": formatted["firebase_uid"], "role": "admin"})
    formatted["access_token"] = token
    formatted["token_type"] = "bearer"
    return formatted

@router.post("/admin/forgot-password")
async def admin_forgot_password(req: AdminForgotRequest):
    return await forgot_password(ForgotPasswordRequest(email=req.email))

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return UserModel.format_for_response(current_user)

@router.put("/ngo/profile", response_model=UserResponse)
async def update_ngo_profile_endpoint(
    profile_update: NgoProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update NGO profile fields."""
    if current_user.get("role") not in ["FOOD_RECEIVER", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Food Receivers can update NGO profile fields"
        )
        
    updated_user = await update_user_profile(current_user["firebase_uid"], profile_update.model_dump())
    return UserModel.format_for_response(updated_user)

@router.put("/volunteer/profile", response_model=UserResponse)
async def update_volunteer_profile_endpoint(
    profile_update: VolunteerProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update Volunteer profile fields."""
    if current_user.get("role") not in ["volunteer", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only volunteers can update volunteer profile fields"
        )
        
    updated_user = await update_user_profile(current_user["firebase_uid"], profile_update.model_dump())
    return UserModel.format_for_response(updated_user)

@router.put("/volunteer/availability", response_model=UserResponse)
async def update_volunteer_availability_endpoint(
    availability_update: VolunteerAvailabilityUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update Volunteer availability status."""
    if current_user.get("role") not in ["volunteer", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only volunteers can update availability"
        )
        
    updated_user = await update_user_profile(current_user["firebase_uid"], availability_update.model_dump())
    return UserModel.format_for_response(updated_user)

@router.put("/fcm-token", response_model=UserResponse)
async def update_fcm_token_endpoint(
    token_update: FcmTokenUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user's FCM token for push notifications."""
    updated_user = await update_user_profile(current_user["firebase_uid"], token_update.model_dump())
    return UserModel.format_for_response(updated_user)
