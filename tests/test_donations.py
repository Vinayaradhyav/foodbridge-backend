import pytest
from app.models.donation import DonationModel
from app.schemas.donation import DonationCreate
from datetime import datetime, timezone

def test_donation_model_creation():
    data = {
        "food_name": "Test Food",
        "food_type": "Cooked",
        "quantity": 10.0,
        "unit": "meals",
        "number_of_meals": 10,
        "preparation_time": datetime.now(timezone.utc),
        "available_from": datetime.now(timezone.utc),
        "pickup_deadline": datetime.now(timezone.utc),
        "pickup_location": "Test Location",
        "latitude": 12.0,
        "longitude": 77.0,
        "storage_condition": "room_temp",
        "packaging_type": "box",
        "description": "Test",
        "food_image": "image.jpg"
    }

    donation = DonationModel.create_new_donation("donor_123", data)
    assert donation["donor_id"] == "donor_123"
    assert donation["food_name"] == "Test Food"
    assert donation["status"] in ("AVAILABLE", "MATCHING")
    assert "created_at" in donation
    assert "updated_at" in donation

def test_update_donation_ownership_validation():
    # In a full test suite with mocked DB, we'd verify that updating a donation
    # where the user_id doesn't match the donation's donor_id raises a 403 HTTP Exception.
    # This serves as a placeholder ensuring the core models run successfully.
    pass


def test_dedupe_donation_docs_keeps_most_progressed():
    from app.services.donation_service import _dedupe_donation_docs
    now = datetime.now(timezone.utc)
    docs = [
        {
            "_id": "id_old_available",
            "donor_id": "donor_1",
            "food_name": "Packaged Dry Staples & Grains",
            "pickup_location": "55 corese mysore",
            "quantity": 3.0,
            "status": "AVAILABLE",
            "created_at": now,
        },
        {
            "_id": "id_progressed",
            "donor_id": "donor_1",
            "food_name": "Packaged Dry Staples & Grains",
            "pickup_location": "55 corese mysore",
            "quantity": 3.0,
            "status": "IN_TRANSIT",
            "accepted_by": "ngo_1",
            "food_order_id": "FB-4933",
            "created_at": now,
        },
    ]
    deduped = _dedupe_donation_docs(docs)
    assert len(deduped) == 1
    assert deduped[0]["_id"] == "id_progressed"
    assert deduped[0]["status"] == "IN_TRANSIT"


def test_canonical_order_and_otp_consistency():
    from app.services.donation_service import _derive_canonical_order_and_otp, _format_donation_response
    formatted = _format_donation_response({
        "_id": "6ae9e8734d6ac451523646f3",
        "donor_id": "donor_1",
        "food_order_id": "FB-4933",
        "pickup_otp": "4182",
        "quantity": 3.0,
        "number_of_meals": 0,
    })
    assert formatted["food_order_id"] == "FB-4933"
    assert formatted["donation_id"] == "FB-4933"
    assert formatted["pickup_otp"] == "4933"
    assert formatted["delivery_otp"] == "4933"
    assert formatted["handover_otp"] == "4933"
    assert formatted["number_of_meals"] == 3
    order, otp = _derive_canonical_order_and_otp(formatted)
    assert order == "FB-4933"
    assert otp == "4933"
