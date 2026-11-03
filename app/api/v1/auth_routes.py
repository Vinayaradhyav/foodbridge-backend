from fastapi import APIRouter, Depends, HTTPException, Header
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
        
    token = authorization.split(" ")[1]
    try:
        user_data = await auth_service.verify_token(token)
        return user_data
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Returns the profile data of the currently authenticated user."""
    return {"user": current_user}
