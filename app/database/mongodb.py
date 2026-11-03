"""
FoodBridge Enterprise Database Connection Manager & Reliability Engine.
Provides resilient connection pooling, active read/write health probes,
automatic reconnection with exponential backoff and randomized jitter,
and continuous telemetry without credential leakage.
"""

import time
import random
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.settings import settings

logger = logging.getLogger("food_bridge.database")

class MongoDBConnectionManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Any = None
    
    # Telemetry and state tracking
    status: str = "DISCONNECTED"  # DISCONNECTED, CONNECTING, HEALTHY, DEGRADED
    connected_at: Optional[datetime] = None
    last_ping_time: Optional[datetime] = None
    last_latency_ms: float = 0.0
    total_reconnect_attempts: int = 0
    consecutive_failures: int = 0
    _monitor_task: Optional[asyncio.Task] = None
    _is_shutting_down: bool = False

    # Collection Accessors (Preserving full backward compatibility)
    @property
    def users(self): return self.db.users if self.db is not None else None
    
    @property
    def donations(self): return self.db.donations if self.db is not None else None
    
    @property
    def receivers(self): return self.db.receivers if self.db is not None else None
    
    @property
    def volunteers(self): return self.db.volunteers if self.db is not None else None
    
    @property
    def emergency_requests(self): return self.db.emergency_requests if self.db is not None else None
    
    @property
    def matches(self): return self.db.matches if self.db is not None else None
    
    @property
    def assignments(self): return self.db.assignments if self.db is not None else None
    
    @property
    def deliveries(self): return self.db.deliveries if self.db is not None else None
    
    @property
    def notifications(self): return self.db.notifications if self.db is not None else None
    
    @property
    def complaints(self): return self.db.complaints if self.db is not None else None
    
    @property
    def food_safety(self): return self.db.food_safety if self.db is not None else None
    
    @property
    def audit_logs(self): return self.db.audit_logs if self.db is not None else None

    @property
    def error_logs(self): return self.db.error_logs if self.db is not None else None

    @property
    def messages(self): return self.db.messages if self.db is not None else None

    @property
    def emergencies(self): return self.db.emergencies if self.db is not None else None

    async def connect(self) -> bool:
        """Establishes MongoDB connection pool with enterprise timeouts and resilience."""
        self._is_shutting_down = False
        self.status = "CONNECTING"
        logger.info(f"[DatabaseManager] Initializing connection to database: {settings.DATABASE_NAME}...")

        try:
            self.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                maxPoolSize=50,
                minPoolSize=5,
                maxIdleTimeMS=45000,
                waitQueueTimeoutMS=5000,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=30000,
                retryWrites=True
            )
            self.db = self.client[settings.DATABASE_NAME]
            
            # Execute active ping probe
            start_t = time.perf_counter()
            await asyncio.wait_for(self.client.admin.command('ping'), timeout=3.0)
            latency = (time.perf_counter() - start_t) * 1000.0
            
            self.last_latency_ms = round(latency, 2)
            self.status = "HEALTHY"
            self.connected_at = datetime.now(timezone.utc)
            self.last_ping_time = datetime.now(timezone.utc)
            self.consecutive_failures = 0
            
            logger.info(f"[DatabaseManager] Connected successfully to MongoDB! (Latency: {self.last_latency_ms} ms)")
            
            # Start background connection monitor
            if self._monitor_task is None or self._monitor_task.done():
                self._monitor_task = asyncio.create_task(self._connection_monitor_loop())
                
            return True
        except Exception as e:
            self.status = "DEGRADED"
            self.consecutive_failures += 1
            logger.warning(f"[DatabaseManager] Initial connection failed: {e}. Entering auto-reconnect mode.")
            if self._monitor_task is None or self._monitor_task.done():
                self._monitor_task = asyncio.create_task(self._connection_monitor_loop())
            return False

    async def _connection_monitor_loop(self):
        """Continuous background monitor with exponential backoff and randomized jitter."""
        logger.info("[DatabaseManager] Background connection watchdog started.")
        while not self._is_shutting_down:
            try:
                if self.status == "HEALTHY":
                    # Periodic lightweight ping probe every 30 seconds
                    await asyncio.sleep(30)
                    start_t = time.perf_counter()
                    await asyncio.wait_for(self.client.admin.command('ping'), timeout=10.0)
                    self.last_latency_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
                    self.last_ping_time = datetime.now(timezone.utc)
                    self.consecutive_failures = 0
                else:
                    # Exponential backoff with jitter: 2s -> 4s -> 8s -> max 30s + [0.1..1.5s] jitter
                    backoff = min(30.0, (2.0 ** min(self.consecutive_failures, 4))) + random.uniform(0.1, 1.5)
                    logger.info(f"[DatabaseManager] Auto-reconnect attempt #{self.total_reconnect_attempts + 1} in {backoff:.2f}s...")
                    await asyncio.sleep(backoff)
                    
                    self.total_reconnect_attempts += 1
                    reconnected = await self._attempt_reconnect()
                    if reconnected:
                        logger.info("[DatabaseManager] Connection successfully restored by background watchdog!")
            except asyncio.CancelledError:
                break
            except Exception as probe_err:
                self.consecutive_failures += 1
                self.status = "DEGRADED"
                logger.warning(f"[DatabaseManager] Watchdog probe failed (#{self.consecutive_failures}): {probe_err}")

    async def _attempt_reconnect(self) -> bool:
        """Internal safe reconnection routine."""
        try:
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
            self.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                maxPoolSize=50,
                minPoolSize=5,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=15000,
                socketTimeoutMS=30000
            )
            self.db = self.client[settings.DATABASE_NAME]
            start_t = time.perf_counter()
            await asyncio.wait_for(self.client.admin.command('ping'), timeout=10.0)
            self.last_latency_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
            self.status = "HEALTHY"
            self.last_ping_time = datetime.now(timezone.utc)
            self.consecutive_failures = 0
            return True
        except Exception as e:
            self.consecutive_failures += 1
            self.status = "DEGRADED"
            return False

    async def check_health(self) -> Dict[str, Any]:
        """Provides non-sensitive telemetry on database health and read/write availability."""
        read_healthy = False
        write_healthy = False
        probe_latency_ms = 0.0

        if self.client is not None and self.db is not None:
            try:
                start_t = time.perf_counter()
                # 1. Read probe
                await asyncio.wait_for(self.db.command('ping'), timeout=8.0)
                read_healthy = True
                
                # 2. Write probe on ephemeral healthcheck record
                await asyncio.wait_for(
                    self.db["_health_probes"].update_one(
                        {"_id": "api_health_sentinel"},
                        {"$set": {"last_probe_at": datetime.now(timezone.utc)}},
                        upsert=True
                    ),
                    timeout=8.0
                )
                write_healthy = True
                probe_latency_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
            except Exception as e:
                logger.warning(f"[DatabaseManager] Health probe exception: {e}")

        return {
            "status": "connected" if (read_healthy and write_healthy) else ("degraded" if read_healthy else "disconnected"),
            "read_healthy": read_healthy,
            "write_healthy": write_healthy,
            "latency_ms": probe_latency_ms if probe_latency_ms > 0 else self.last_latency_ms,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_ping": self.last_ping_time.isoformat() if self.last_ping_time else None,
            "consecutive_failures": self.consecutive_failures,
            "reconnect_attempts": self.total_reconnect_attempts
        }

    async def close(self):
        """Clean shutdown terminating background tasks and connection pools."""
        self._is_shutting_down = True
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        if self.client:
            logger.info("[DatabaseManager] Terminating MongoDB connection pool...")
            self.client.close()
            self.status = "DISCONNECTED"
            logger.info("[DatabaseManager] MongoDB pool closed cleanly.")


# Global singleton instance
mongodb = MongoDBConnectionManager()

async def connect_to_mongo():
    await mongodb.connect()

async def close_mongo_connection():
    await mongodb.close()

def get_database():
    return mongodb.db
