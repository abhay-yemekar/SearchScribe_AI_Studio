from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from .routers import auth_routes, content_routes

app = FastAPI(
    title="SearchScribe AI Studio API",
    version="1.0.0",
)

# Frontend runs on http://localhost:3000
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "message": "Backend is running successfully!"}


# Routers
app.include_router(auth_routes.router)
app.include_router(content_routes.router)

# Simple startup log for Gemini
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    print("\n⚠ WARNING: GEMINI_API_KEY not found in .env — LLM calls will fail.\n")
else:
    print("\n✅ Gemini API Key loaded.\n")
