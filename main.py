
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.config import settings
from core.exceptions import (
    APIException,
    api_exception_handler,
    global_exception_handler
)
from api import auth, playlists

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Headless CMS extending Spotify Web API "
        "with internal RBAC and multimedia BLOB mapping."
    ),
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Register global exception handlers
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Register application routers
app.include_router(auth.router)
app.include_router(playlists.router)


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "operational",
        "service": "Spotify CMS"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        access_log=False
    )
