
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="SABBIR MAXTAN Download Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production-এ নির্দিষ্ট origin ব্যবহার করবে
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {
        "app": "SABBIR MAXTAN Download Engine",
        "status": "online"
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/download/status")
def download_status():
    return {
        "status": "ready",
        "message": "Backend connection successful"
    }
