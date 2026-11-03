from datetime import datetime, timezone
from typing import List, Dict, Any
from bson import ObjectId
from app.database.mongodb import mongodb
from app.ai.fraud.predictor import fraud_predictor

# Initial seed anomalies for demonstration if database is empty
DEMO_ANOMALIES = [
    {
        "user_id": "usr_phantom_991",
        "user_name": "Metro Grand Banquets (Unverified)",
        "user_role": "DONOR",
        "risk_level": "HIGH_RISK",
        "risk_score": 92,
        "reasons": [
            "Extremely high quantity per donation (>5000 items).",
            "Abnormally large listing quantity on a brand new account.",
            "Unsupervised AI (Isolation Forest) flagged transaction telemetry as an outlier."
        ],
        "related_transaction": "Listed 6,200 meals • Claimed then canceled 4 times",
        "status": "OPEN",
        "timestamp": datetime.now(timezone.utc)
    },
    {
        "user_id": "usr_multi_ip_402",
        "user_name": "Apex Food Redistribution Cell",
        "user_role": "NGO",
        "risk_level": "SUSPICIOUS",
        "risk_score": 64,
        "reasons": [
            "Multiple accounts detected operating on the same IP (4 accounts).",
            "Unusual geographic velocity variance / location hopping.",
            "High cancellation frequency (5 cancels, 45% ratio)."
        ],
        "related_transaction": "Claimed 8 donations across disparate zones within 15 mins",
        "status": "OPEN",
        "timestamp": datetime.now(timezone.utc)
    },
    {
        "user_id": "usr_spoilage_abuse_118",
        "user_name": "City Quick Foods",
        "user_role": "DONOR",
        "risk_level": "SUSPICIOUS",
        "risk_score": 55,
        "reasons": [
            "Repeated image inspection rejections (3 failed uploads with non-food/spoilage).",
            "High cancellation frequency (4 cancels, 40% ratio)."
        ],
        "related_transaction": "3 flagged image rejections by AI Computer Vision",
        "status": "OPEN",
        "timestamp": datetime.now(timezone.utc)
    }
]

class AnomalyService:
    @staticmethod
    async def run_system_scan() -> None:
        """
        Scans all users and their recent activity to detect anomalies and store them.
        """
        try:
            if mongodb.db is None:
                return

            # Check if anomalies collection is empty
            count = await mongodb.db.anomalies.count_documents({})
            if count == 0:
                for demo in DEMO_ANOMALIES:
                    await mongodb.db.anomalies.insert_one(demo.copy())

            # Fetch active users
            users = await mongodb.db.users.find({"status": {"$ne": "suspended"}}).to_list(length=1000)

            for user in users:
                uid = user.get("firebase_uid") or str(user.get("_id"))
                if not uid:
                    continue

                # Query donations by this user
                donations = await mongodb.db.donations.find({"donor_id": uid}).to_list(length=100)
                if not donations:
                    continue

                daily_dons = len(donations)
                quantities = [float(d.get("quantity", 0)) for d in donations]
                avg_qty = sum(quantities) / max(1, len(quantities))
                max_qty = max(quantities) if quantities else avg_qty
                cancellations = sum(1 for d in donations if d.get("status") == "CANCELLED")
                cancel_ratio = cancellations / max(1, len(donations))

                data = {
                    "daily_donations": daily_dons,
                    "avg_quantity": avg_qty,
                    "max_quantity": max_qty,
                    "cancellations": cancellations,
                    "cancel_ratio": cancel_ratio,
                    "distance_variance": 5.0,
                    "duplicate_ips": 1,
                    "account_age_days": 30.0
                }

                prediction = fraud_predictor.analyze(data)

                if prediction["classification"] in ["HIGH_RISK", "SUSPICIOUS"]:
                    existing = await mongodb.db.anomalies.find_one({
                        "user_id": uid,
                        "status": {"$in": ["OPEN", "REVIEWING"]}
                    })

                    if not existing:
                        anomaly_doc = {
                            "user_id": uid,
                            "user_name": user.get("name", "Unknown Stakeholder"),
                            "user_role": user.get("role", "DONOR"),
                            "risk_level": prediction["classification"],
                            "risk_score": prediction["risk_score"],
                            "reasons": prediction["reasons"],
                            "related_transaction": f"{len(donations)} donations • Max {int(max_qty)} items",
                            "status": "OPEN",
                            "timestamp": datetime.now(timezone.utc)
                        }
                        await mongodb.db.anomalies.insert_one(anomaly_doc)

        except Exception as e:
            print(f"[AnomalyService] System scan exception: {e}")

    @staticmethod
    async def get_all_anomalies() -> List[Dict[str, Any]]:
        try:
            if mongodb.db is None:
                # Return demo anomalies with simulated string IDs
                res = []
                for i, d in enumerate(DEMO_ANOMALIES):
                    item = d.copy()
                    item["id"] = f"demo_anomaly_{i+1}"
                    item["timestamp"] = item["timestamp"].isoformat()
                    res.append(item)
                return res

            cursor = mongodb.db.anomalies.find().sort("timestamp", -1)
            anomalies = await cursor.to_list(length=1000)

            if not anomalies:
                for demo in DEMO_ANOMALIES:
                    await mongodb.db.anomalies.insert_one(demo.copy())
                cursor = mongodb.db.anomalies.find().sort("timestamp", -1)
                anomalies = await cursor.to_list(length=1000)

            for a in anomalies:
                a["id"] = str(a.pop("_id"))
                if isinstance(a.get("timestamp"), datetime):
                    a["timestamp"] = a["timestamp"].isoformat()

            return anomalies
        except Exception as e:
            print(f"[AnomalyService] get_all_anomalies error: {e}")
            res = []
            for i, d in enumerate(DEMO_ANOMALIES):
                item = d.copy()
                item["id"] = f"fallback_{i+1}"
                item["timestamp"] = item["timestamp"].isoformat()
                res.append(item)
            return res

    @staticmethod
    async def update_anomaly_status(anomaly_id: str, new_status: str, admin_id: str) -> bool:
        try:
            if mongodb.db is None:
                return True

            try:
                oid = ObjectId(anomaly_id)
                query = {"_id": oid}
            except Exception:
                query = {"user_id": anomaly_id}

            result = await mongodb.db.anomalies.update_one(
                query,
                {"$set": {
                    "status": new_status,
                    "resolved_by": admin_id,
                    "resolved_at": datetime.now(timezone.utc)
                }}
            )
            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            print(f"[AnomalyService] update status error: {e}")
            return False

    @staticmethod
    async def suspend_user(anomaly_id: str, admin_id: str) -> bool:
        try:
            if mongodb.db is None:
                return True

            try:
                oid = ObjectId(anomaly_id)
                anomaly = await mongodb.db.anomalies.find_one({"_id": oid})
            except Exception:
                anomaly = await mongodb.db.anomalies.find_one({"user_id": anomaly_id})

            if not anomaly:
                return False

            uid = anomaly["user_id"]

            await mongodb.db.users.update_one(
                {"firebase_uid": uid},
                {"$set": {"status": "suspended", "suspended_at": datetime.now(timezone.utc)}}
            )

            await AnomalyService.update_anomaly_status(anomaly_id, "USER_SUSPENDED", admin_id)

            await mongodb.db.audit_logs.insert_one({
                "action": "USER_SUSPENDED_FROM_ANOMALY",
                "user_id": uid,
                "admin_id": admin_id,
                "anomaly_id": anomaly_id,
                "timestamp": datetime.now(timezone.utc),
                "details": f"User suspended due to AI anomaly flags: {', '.join(anomaly.get('reasons', []))}"
            })

            return True
        except Exception as e:
            print(f"[AnomalyService] suspend user error: {e}")
            return False
