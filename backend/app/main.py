from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title="Traffic AI API",
    version="0.3.0",
    description="Backend API for the traffic vehicle detection, tracking and counting project.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://traffic-ai.test:8443",
        "https://traffic-ai.test:8444",
        "https://localhost:8443",
        "https://localhost:8444",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": "0.3.0",
        "docs": "/docs",
        "health": "/api/health",
    }
