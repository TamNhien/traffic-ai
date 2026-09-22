from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="Traffic AI Service", version="0.1.3")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ready",
        "service": "ai-service",
        "pipeline": "scaffold",
        "detector": "pending-v0.2",
        "tracker": "pending-v0.2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
