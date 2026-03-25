import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.routers import health, auth, import_, tournaments, hands, villains
from app.routers.entries import router as entries_router

load_dotenv()

app = FastAPI(title="Poker App API", version="0.1.0")

allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(import_.router)
app.include_router(tournaments.router)
app.include_router(hands.router)
app.include_router(villains.router)
app.include_router(entries_router)

@app.get("/")
def root():
    return {"app": "poker-app", "version": "0.1.0"}
