from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ask, health

app = FastAPI(title="KPI Copilot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

app.include_router(health.router)
app.include_router(ask.router)

@app.get("/")
def root():
    return {"ok": True}