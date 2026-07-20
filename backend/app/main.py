import os
import sys
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure Python path compatibility dynamically to ensure scripts can be loaded
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = None
while current_dir and current_dir != os.path.dirname(current_dir):
    if os.path.exists(os.path.join(current_dir, "scripts")):
        project_root = current_dir
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        break
    current_dir = os.path.dirname(current_dir)

# Import SpecError from scripts
try:
    from scripts.flowdraft.schema import SpecError
except ImportError:
    # Fallback to keep startup safe if imports are messed up in other environments
    class SpecError(Exception):
        pass

# Import routers
from app.api.v1.auth import router as auth_router
from app.api.v1.diagrams import router as diagrams_router
from app.api.v1.exports import router as exports_router
from app.api.v1.mcp import mcp, make_mcp_asgi_app
from app.core.config import settings
from fastapi import FastAPI, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="FlowDraft Gateway API",
    description="Gateway API for FlowDraft rendering engine and diagrams repository",
    version="1.0.0",
)

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP API Key validation middleware
@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next):
    if request.url.path.startswith(("/api/v1/mcp", "/api/mcp")):
        api_key = request.headers.get("X-MCP-API-Key") or request.query_params.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "MCP API Key is missing"}
            )
        allowed_keys = [k.strip() for k in settings.MCP_API_KEYS.split(",") if k.strip()]
        if api_key not in allowed_keys:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid MCP API Key"}
            )
    return await call_next(request)

# Custom exception handler for SpecError to return HTTP 400 Bad Request
@app.exception_handler(SpecError)
async def spec_error_exception_handler(request, exc: SpecError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": exc.reason,
            "path": getattr(exc, "path", None)
        }
    )

# Root route
@app.get("/")
def read_root():
    return {"message": "FlowDraft Gateway API is running"}

@app.get("/health")
async def health_check():
    from app.services.redis_broker import RedisBroker
    from app.api.deps import get_db
    from sqlalchemy.future import select

    broker = RedisBroker()
    redis_ok = await broker.ping()

    db_ok = False
    db_err = None
    try:
        get_db_fn = app.dependency_overrides.get(get_db, get_db)
        db_gen = get_db_fn()
        if hasattr(db_gen, "__anext__"):
            db = await db_gen.__anext__()
            try:
                await db.execute(select(1))
                db_ok = True
            finally:
                try:
                    await db_gen.__anext__()
                except StopAsyncIteration:
                    pass
        else:
            db = db_gen
            await db.execute(select(1))
            db_ok = True
    except Exception as e:
        db_err = str(e)

    if redis_ok and db_ok:
        return {"status": "healthy"}
    else:
        content = {"status": "unhealthy"}
        if not redis_ok:
            content["redis"] = "offline"
        if not db_ok:
            content["database"] = f"offline: {db_err}"
        return JSONResponse(
            status_code=500,
            content=content
        )

# Include routers
# /api/v1 prefix
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(diagrams_router, prefix="/api/v1/diagrams", tags=["diagrams"])
app.include_router(exports_router, prefix="/api/v1/export", tags=["exports"])

# /api prefix
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(diagrams_router, prefix="/api/diagrams", tags=["diagrams"])
app.include_router(exports_router, prefix="/api/export", tags=["exports"])

# Mount FastMCP SSE applications
app.mount("/api/v1/mcp", make_mcp_asgi_app("/api/v1/mcp"))
app.mount("/api/mcp", make_mcp_asgi_app("/api/mcp"))


