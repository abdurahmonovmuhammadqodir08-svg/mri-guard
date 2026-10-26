import os

SECRET_KEY = os.environ.get("SECRET_KEY", "abdurahmonovmuhammadqodirdilshodbekoglimuhammadqodir20092002")
if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY kamida 32 belgidan iborat bo'lishi shart (.env faylini tekshiring)")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./mri_guard.db")
ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", 15))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", 10)) * 1024 * 1024
MODEL_PATH = os.environ.get("MODEL_PATH", "models/brain_tumor.pt")
DETECTION_THRESHOLD = float(os.environ.get("DETECTION_THRESHOLD", 0.35))
STORAGE_DIR = "storage"
CLASSES = ["glioma", "meningioma", "notumor", "pituitary"]
