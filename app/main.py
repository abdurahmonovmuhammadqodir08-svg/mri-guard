import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from . import config
from .database import Base, engine
from .routers import auth, scans, admin
from .ml import pipeline

os.makedirs(config.STORAGE_DIR, exist_ok=True)
Base.metadata.create_all(engine)

app = FastAPI(title="MRI-Guard", docs_url=None, redoc_url=None)  # productionda docs yopiq
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=["https://localhost:3000"],
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    r = await call_next(request)
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"] = "DENY"
    r.headers["Referrer-Policy"] = "no-referrer"
    r.headers["Content-Security-Policy"] = "default-src 'self'"
    r.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    r.headers["Cache-Control"] = "no-store"
    return r


@app.on_event("startup")
def startup():
    print("Model yuklandi" if pipeline.load_model() else "OGOHLANTIRISH: model topilmadi")


app.include_router(auth.router)
app.include_router(scans.router)
app.include_router(admin.router)


# Frontend (eng oxirida, API yo'llaridan keyin)
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
