from fastapi import FastAPI

app = FastAPI(title="Athos Fitness Platform API")

@app.get("/health")
def health():
    return {"status": "ok"}