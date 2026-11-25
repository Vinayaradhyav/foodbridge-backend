"""
FoodBridge NLP V2 — Telemetry, Performance Monitoring & Audit Logging
Records live inference requests, tracks latencies, drift metrics,
and persists telemetry to MongoDB collection 'nlp_audit_logs'.
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import deque, Counter

# In-memory circular buffer for fast zero-IO telemetry queries
_RECENT_INFERENCES = deque(maxlen=200)

class NLPMonitor:
    """Collects and reports real-time inference telemetry and quality metrics."""

    @staticmethod
    async def log_inference(
        result: Dict[str, Any],
        client_ip: Optional[str] = "127.0.0.1",
        user_id: Optional[str] = None
    ):
        """Asynchronously records an inference record to memory and MongoDB."""
        record = {
            "request_id": result.get("request_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": result.get("processing_time_ms", 0.0),
            "intent": result.get("intent"),
            "confidence": result.get("confidence", 0.0),
            "is_complete": result.get("completeness", {}).get("is_complete", False),
            "missing_fields": result.get("completeness", {}).get("missing_fields", []),
            "priority_score": result.get("priority", {}).get("score", 0),
            "priority_level": result.get("priority", {}).get("priority_level", "LOW"),
            "action": result.get("action_recommendation"),
            "client_ip": client_ip,
            "user_id": user_id
        }

        # Store in fast memory queue
        _RECENT_INFERENCES.append(record)

        # Async persist to MongoDB if available
        try:
            from app.database import mongodb
            if mongodb.db is not None:
                await mongodb.db.nlp_audit_logs.insert_one(record)
        except Exception:
            pass  # Do not block request on audit logging failure

    @staticmethod
    def get_summary_metrics() -> Dict[str, Any]:
        """Calculates real-time performance summary from recent inference buffer."""
        total = len(_RECENT_INFERENCES)
        if total == 0:
            return {
                "total_inferences": 0,
                "average_latency_ms": 0.0,
                "intent_distribution": {},
                "priority_distribution": {},
                "completeness_rate": 100.0,
                "recent_records": []
            }

        latencies = [r["latency_ms"] for r in _RECENT_INFERENCES]
        avg_lat = round(sum(latencies) / total, 2)
        intents = Counter(r["intent"] for r in _RECENT_INFERENCES)
        priorities = Counter(r["priority_level"] for r in _RECENT_INFERENCES)
        complete_count = sum(1 for r in _RECENT_INFERENCES if r["is_complete"])

        return {
            "total_inferences_recorded": total,
            "average_latency_ms": avg_lat,
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "completeness_rate_pct": round((complete_count / total) * 100, 1),
            "intent_distribution": dict(intents),
            "priority_distribution": dict(priorities),
            "recent_records": list(reversed(list(_RECENT_INFERENCES)))[:15]
        }


nlp_monitor = NLPMonitor()
