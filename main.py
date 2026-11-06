
from fastapi import FastAPI
import uvicorn

from core.exceptions import (
    APIException,
    api_exception_handler,
    global_exception_handler,
)

app = FastAPI(
    title="Spotify API Aggregator CMS",
    description="Headless CMS extending Spotify Web API with internal RBAC and multimedia BLOB mapping.",
    version="1.0.0",
)

# Register application exception handlers.
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "operational",
        "service": "Spotify CMS",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
