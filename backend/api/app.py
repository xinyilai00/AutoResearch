from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes_stages import router as stages_router


app = FastAPI(title="AutoResearch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stages_router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
