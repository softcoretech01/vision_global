import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .routers import auth, enquiries, proposals, quotations, config, dashboard, whatsapp
from . import scheduler
from .storage import UPLOAD_DIR

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()       # begin background auto-fetch
    yield
    scheduler.stop()


app = FastAPI(title="Vision Global API", version="1.0.0", lifespan=lifespan)

origins = [o for o in os.environ.get("CORS_ORIGIN", "http://localhost:5173").split(",") if o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "vision-global-api", "framework": "fastapi"}


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(enquiries.router, prefix="/api/enquiries", tags=["enquiries"])
app.include_router(proposals.router, prefix="/api/proposals", tags=["proposals"])
app.include_router(quotations.router, prefix="/api/quotations", tags=["quotations"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["whatsapp"])
