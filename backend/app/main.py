from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.workouts import router as workouts_router
from app.db.session import get_db

app = FastAPI(title="Athos Fitness Platform API")
app.include_router(auth_router)
app.include_router(workouts_router)
app.include_router(dashboard_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"db": "ok"}
