"""Hujumni aniqlash va tozalash pipeline'i (v2).

Diagnostika asosida: bit-chuqurligi va kichik median filtr kuchli hujumga ta'sir qilmadi,
down/up (kichraytirib qayta kattalashtirish) va xiralashtirish esa to'g'ri javobni qaytardi.
Aniqlash: tasvirni down/up va blur dan o'tkazib, bashorat ehtimolliklari orasidagi farq (L1).
Tozalash: down/up. Ikkinchi tozalash (blur) bilan kelishuv va qolgan ball tekshiriladi.
"""
import io
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageFilter
from scipy.ndimage import median_filter
from torchvision import models
from .. import config

IMG_SIZE = 224
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
MIN_PURIFIED_CONF = 0.60

_model = None
_classes = config.CLASSES


class Normalized(nn.Module):
    """src/models.py dagi bilan bir xil (state kalitlari mos tushishi uchun)."""
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.register_buffer("mean", torch.tensor(MEAN).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor(STD).view(1, 3, 1, 1))

    def forward(self, x):
        return self.model((x - self.mean) / self.std)


def _build_resnet50(num_classes):
    m = models.resnet50(weights=None)
    m.fc = nn.Linear(m.fc.in_features, num_classes)
    return Normalized(m)


def load_model():
    global _model, _classes
    try:
        ck = torch.load(config.MODEL_PATH, map_location="cpu", weights_only=True)
        _classes = list(ck["classes"])
        m = _build_resnet50(len(_classes))
        m.load_state_dict(ck["state"])
        _model = m.eval()
    except Exception as e:
        print("Model yuklashda xato:", e)
        _model = None
    return _model is not None


def _to_array(img: Image.Image) -> np.ndarray:
    g = img.convert("L").convert("RGB").resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    return np.asarray(g, dtype=np.float32) / 255.0


def _to_pil(x: np.ndarray) -> Image.Image:
    return Image.fromarray((np.clip(x, 0, 1) * 255).round().astype(np.uint8))


def _predict_proba(x: np.ndarray) -> np.ndarray:
    t = torch.from_numpy(x.transpose(2, 0, 1).copy()).unsqueeze(0)
    with torch.no_grad():
        return F.softmax(_model(t), dim=1)[0].numpy()


# Diagnostika skripti uchun saqlangan yordamchilar
def _bit_depth(x, bits=4):
    levels = 2 ** bits - 1
    return np.round(x * levels) / levels


def _median(x, k=2):
    return np.stack([median_filter(x[..., c], size=k) for c in range(3)], axis=-1)


def _downup(x: np.ndarray) -> np.ndarray:
    im = _to_pil(x).resize((112, 112), Image.BILINEAR).resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    return np.asarray(im, dtype=np.float32) / 255.0


def _blur(x: np.ndarray) -> np.ndarray:
    return np.asarray(_to_pil(x).filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255.0


SQUEEZERS = (_downup, _blur)


def detection_score(x: np.ndarray) -> float:
    p = _predict_proba(x)
    return float(max(np.abs(p - _predict_proba(s(x))).sum() for s in SQUEEZERS))


def analyze(img: Image.Image) -> dict:
    if _model is None:
        raise RuntimeError("Model yuklanmagan")
    x = _to_array(img)
    score = detection_score(x)
    attacked = score > config.DETECTION_THRESHOLD
    result = {"attack_detected": bool(attacked), "detection_score": score,
              "purified": False, "residual_score": None, "status": "processed"}
    if attacked:
        xp = _downup(x)
        p = _predict_proba(xp)
        p_alt = _predict_proba(_blur(x))          # ikkinchi, mustaqil tozalash
        residual = detection_score(xp)
        agree = int(p.argmax()) == int(p_alt.argmax())
        result.update(purified=True, residual_score=float(residual))
        if residual > config.DETECTION_THRESHOLD or not agree or float(p.max()) < MIN_PURIFIED_CONF:
            result["status"] = "needs_review"
    else:
        p = _predict_proba(x)
    i = int(p.argmax())
    result.update(prediction=_classes[i], confidence=float(p[i]))
    return result