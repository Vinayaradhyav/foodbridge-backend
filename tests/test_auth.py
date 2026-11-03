import pytest
from app.models.user import UserModel
from app.core.security import require_role
from fastapi import HTTPException

def test_user_model_creation():
    user = UserModel.create_new_user(
        firebase_uid="test_uid_123",
        name="John Doe",
        email="john@example.com",
        phone="1234567890",
        role="donor"
    )
    assert user["firebase_uid"] == "test_uid_123"
    assert user["name"] == "John Doe"
    assert user["role"] == "donor"
    assert user["status"] == "active"
    assert "created_at" in user

@pytest.mark.anyio
async def test_role_checker_dependency():
    role_checker = require_role(["admin", "ngo"])
    
    # Valid user role
    valid_user = {"role": "admin"}
    result = await role_checker(valid_user)
    assert result == valid_user
    
    # Invalid user role
    invalid_user = {"role": "donor"}
    with pytest.raises(HTTPException) as excinfo:
        await role_checker(invalid_user)
    assert excinfo.value.status_code == 403
    assert "Operation not permitted" in excinfo.value.detail
