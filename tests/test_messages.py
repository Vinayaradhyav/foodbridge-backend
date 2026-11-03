import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_messages_workflow():
    with TestClient(app) as client:
        # 1. Send message from donor to receiver
        payload = {
            "recipient_id": "mock_ngo_hope",
            "text": "Hello, when can you pick up the cooked rice donation?",
            "context_type": "DONATION",
            "context_id": "DON-001",
            "sender_name": "Vinay Aradhya",
            "recipient_name": "Hope Foundation"
        }
        res = client.post(
            "/api/messages",
            json=payload,
            headers={"Authorization": "Bearer mock_donor_vinay"}
        )
        assert res.status_code in [200, 201]
        msg = res.json()
        assert msg["text"] == payload["text"]
        assert msg["sender_id"] == "mock_donor_vinay"
        assert msg["recipient_id"] == "mock_ngo_hope"
        conv_id = msg["conversation_id"]

        # 2. Fetch conversation messages as receiver
        res_msgs = client.get(
            f"/api/messages/conversation/{conv_id}",
            headers={"Authorization": "Bearer mock_ngo_hope"}
        )
        assert res_msgs.status_code == 200
        history = res_msgs.json()
        assert len(history) >= 1
        assert any(m["message_id"] == msg["message_id"] for m in history)

        # 3. Receiver replies
        reply_payload = {
            "recipient_id": "mock_donor_vinay",
            "text": "We will dispatch our volunteer within 30 minutes.",
            "conversation_id": conv_id,
            "context_type": "DONATION",
            "context_id": "DON-001"
        }
        res_reply = client.post(
            "/api/messages",
            json=reply_payload,
            headers={"Authorization": "Bearer mock_ngo_hope"}
        )
        assert res_reply.status_code in [200, 201]

        # 4. Mark conversation as read
        res_read = client.post(
            "/api/messages/mark-read",
            json={"conversation_id": conv_id},
            headers={"Authorization": "Bearer mock_ngo_hope"}
        )
        assert res_read.status_code == 200

        # 5. List conversations
        res_convs = client.get(
            "/api/messages/conversations",
            headers={"Authorization": "Bearer mock_donor_vinay"}
        )
        assert res_convs.status_code == 200
        convs = res_convs.json()
        assert len(convs) >= 1
