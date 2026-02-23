import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.workouts import router as workouts_router
from app.db.session import get_db
from app.middleware.request_logging import RequestLoggingMiddleware

app = FastAPI(title="Athos Fitness Platform API")
logging.basicConfig(level=logging.INFO)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Client-Timezone"],
)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(auth_router)
app.include_router(workouts_router)
app.include_router(dashboard_router)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"db": "ok"}
