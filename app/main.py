import time
import uuid
import logging
from collections import defaultdict
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from app.database.mongodb import connect_to_mongo, close_mongo_connection, mongodb
from app.core.firebase_config import initialize_firebase, get_firebase_status

logger = logging.getLogger("food_bridge")
logging.basicConfig(level=logging.INFO)

# ==================== RATE LIMITING CONFIGURATION (Item 8) ====================
RATE_LIMIT_WINDOW = 60  # seconds
LIMITS = {
    "auth": 20,         # login, register, token refresh
    "sensitive": 10,    # password reset, verify email
    "ai": 30,           # image analysis, caption check, matching
    "general": 150      # general reading/browsing
}

_ip_timestamps = {
    "auth": defaultdict(list),
    "sensitive": defaultdict(list),
    "ai": defaultdict(list),
    "general": defaultdict(list)
}

# In-memory recent error trace buffer (Item 15)
_recent_error_logs = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    initialize_firebase()
    yield
    await close_mongo_connection()

app = FastAPI(
    title="Food-Bridge API",
    description="Enterprise API for Food-Bridge - Hardened with RLS, Rate Limiting & Real JWT",
    version="1.1.0",
    lifespan=lifespan
)

# ==================== RATE LIMITING & SECURITY HEADERS (Item 8) ====================
@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    # Allow CORS preflight OPTIONS requests to proceed without rate limiting or size limits
    if request.method == "OPTIONS":
        return await call_next(request)

    # Reject oversized request bodies (> 25 MB)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 25 * 1024 * 1024:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"detail": "Payload too large. Maximum allowed size is 25MB."}
        )

    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path.lower()
    now = time.time()

    # Determine rate limit category
    category = "general"
    if any(p in path for p in ["/forgot-password", "/reset-password", "/verify-email", "/send-verification"]):
        category = "sensitive"
    elif any(p in path for p in ["/auth/login", "/auth/admin/login", "/auth/register"]):
        category = "auth"
    elif "/ai/" in path or "/check-caption" in path or "/matching" in path:
        category = "ai"

    # Clean old timestamps
    max_allowed = LIMITS[category]
    timestamps = [t for t in _ip_timestamps[category][client_ip] if now - t < RATE_LIMIT_WINDOW]
    _ip_timestamps[category][client_ip] = timestamps

    if len(timestamps) >= max_allowed:
        retry_after = int(RATE_LIMIT_WINDOW - (now - timestamps[0]))
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": f"Rate limit exceeded for {category} operations. Please wait {max(1, retry_after)} seconds before retrying.",
                "rate_limit_category": category,
                "limit": max_allowed
            },
            headers={
                "Retry-After": str(max(1, retry_after)),
                "X-RateLimit-Limit": str(max_allowed),
                "X-RateLimit-Remaining": "0"
            }
        )

    _ip_timestamps[category][client_ip].append(now)

    response: Response = await call_next(request)

    # Inject Anti-Hacking & Browser Hardening Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=()"
    response.headers["X-RateLimit-Limit"] = str(max_allowed)
    response.headers["X-RateLimit-Remaining"] = str(max(0, max_allowed - len(timestamps) - 1))
    
    if "server" in response.headers:
        del response.headers["server"]

    return response

# ==================== ERROR TRACKING & CLEAR ERROR MESSAGES (Items 6 & 15) ====================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats human-friendly validation error messages."""
    error_messages = []
    for error in exc.errors():
        field = " -> ".join([str(loc) for loc in error.get("loc", []) if loc != "body"])
        msg = error.get("msg", "Invalid value")
        if "value is not a valid email address" in msg:
            error_messages.append("Please provide a valid email address (e.g. name@example.com).")
        elif "ensure this value has at least" in msg:
            error_messages.append(f"'{field}' does not meet the minimum length requirement.")
        elif "field required" in msg:
            error_messages.append(f"Field '{field}' is required.")
        else:
            error_messages.append(f"{field}: {msg}" if field else msg)

    friendly_detail = " | ".join(error_messages) if error_messages else "Invalid request data submitted."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": friendly_detail, "validation_errors": error_messages}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Centralized error tracker logging unhandled runtime faults with unique reference ID."""
    error_id = f"FB-ERR-{uuid.uuid4().hex[:8].upper()}"
    error_record = {
        "error_id": error_id,
        "path": str(request.url.path),
        "method": request.method,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    logger.error(f"[{error_id}] Runtime Exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    _recent_error_logs.append(error_record)
    if len(_recent_error_logs) > 100:
        _recent_error_logs.pop(0)

    # Async persist in Mongo error_logs if connected
    if mongodb.db is not None:
        try:
            await mongodb.db.error_logs.insert_one(error_record)
        except Exception:
            pass

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": f"A server error occurred. Please contact Food-Bridge support referencing error code: {error_id}",
            "error_id": error_id
        }
    )

# Strict Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_origin_regex=r"^https?://.*$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Authorization", "X-Total-Count", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    max_age=86400,
)

_server_start_time = time.time()

@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "Food-Bridge Enterprise Cloud Core API",
        "status": "online_24_7",
        "authoritative_database": "MongoDB Atlas",
        "documentation": "/docs",
        "health": "/api/health"
    }

@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Centralized health check reporting uptime, database read/write status, and external services."""
    db_health = await mongodb.check_health()
    fb_status = get_firebase_status()
    uptime = round(time.time() - _server_start_time, 2)
    is_healthy = db_health.get("read_healthy", False)

    return JSONResponse(
        status_code=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if is_healthy else "degraded",
            "service": "Food-Bridge Enterprise Core API",
            "version": "1.2.0",
            "uptime_seconds": uptime,
            "database": db_health,
            "firebase": fb_status,
            "security": "Hardened RBAC + Rate-Limited + Error-Tracked",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

@app.get("/ready", tags=["Health"])
@app.get("/api/ready", tags=["Health"])
async def readiness_check():
    """Kubernetes / Cloud Readiness Probe confirming whether the server can safely accept traffic."""
    db_health = await mongodb.check_health()
    can_serve = db_health.get("read_healthy", False) and db_health.get("write_healthy", False)
    
    if can_serve:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "ready": True,
                "status": "operational",
                "database_status": db_health.get("status"),
                "latency_ms": db_health.get("latency_ms"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "ready": False,
                "status": "reconnecting",
                "detail": "Database is reconnecting or degraded. Service temporarily unavailable.",
                "reconnect_attempts": db_health.get("reconnect_attempts", 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

@app.get("/api/health/firebase", tags=["Health"])
async def firebase_health_check():
    """Dedicated diagnostic endpoint for Firebase Admin SDK connectivity."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=get_firebase_status()
    )

@app.get("/api/audit/errors", tags=["Audit"])
async def get_recent_errors():
    """Retrieve recent server runtime error logs (Item 15: Error tracking)."""
    return {"count": len(_recent_error_logs), "errors": list(reversed(_recent_error_logs))}

# ==================== ROUTERS ====================
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.donations import router as donations_router
from app.api.assignments import router as assignments_router
from app.api.notifications import router as notifications_router
from app.api.emergencies import router as emergencies_router
from app.api.ai_emergency import router as ai_emergency_router
from app.api.ai import router as ai_router
from app.api.priority import router as priority_router
from app.api.matching import router as matching_router
from app.api.food_safety import router as food_safety_router
from app.api.food_image import router as food_image_router
from app.api.fraud import router as fraud_router
from app.api.assignment_optimization import router as assignment_optimization_router
from app.api.chatbot import router as chatbot_router
from app.api.analytics import router as analytics_router
from app.api.audit import router as audit_router
from app.api.messages import router as messages_router
from app.api.caption_checker import router as caption_checker_router
from app.api.backup import router as backup_router

from app.api.v1.auth_routes import router as auth_v1_router
from app.api.v1.ngo_routes import router as ngo_v1_router
from app.api.v1.donation_routes import router as donation_v1_router

app.include_router(auth_v1_router, prefix="/api/v1")
app.include_router(ngo_v1_router, prefix="/api/v1")
app.include_router(donation_v1_router, prefix="/api/v1")

app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(donations_router, prefix="/api")
app.include_router(assignments_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(messages_router, prefix="/api")
app.include_router(emergencies_router, prefix="/api")
app.include_router(ai_emergency_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(priority_router, prefix="/api")
app.include_router(matching_router, prefix="/api/matching")
app.include_router(food_safety_router, prefix="/api/ai")
app.include_router(food_image_router, prefix="/api/ai")
app.include_router(caption_checker_router, prefix="/api")
app.include_router(fraud_router, prefix="/api/ai")
app.include_router(fraud_router, prefix="/api")
app.include_router(assignment_optimization_router, prefix="/api/ai")
app.include_router(assignment_optimization_router, prefix="/api")
app.include_router(chatbot_router, prefix="/api/ai")
app.include_router(chatbot_router, prefix="/api/chatbot")
app.include_router(analytics_router, prefix="/api/analytics")
app.include_router(analytics_router, prefix="/api/ai/analytics")
app.include_router(audit_router, prefix="/api")
app.include_router(backup_router, prefix="/api")
