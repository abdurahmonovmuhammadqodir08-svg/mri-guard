import os, io
os.environ.setdefault("SECRET_KEY", "faqat-sinov-uchun-vaqtinchalik-kalit-1234567890")
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageFilter
from torchvision import models
from app.ml import pipeline as P

P.load_model()
MAIN = P._model
CLASSES = P._classes


def load_any(path):
    ck = torch.load(path, map_location="cpu", weights_only=True)
    name = ck["model"]
    if name == "resnet50":
        m = models.resnet50(weights=None); m.fc = nn.Linear(m.fc.in_features, 4)
    elif name == "efficientnet_b0":
        m = models.efficientnet_b0(weights=None); m.classifier[1] = nn.Linear(m.classifier[1].in_features, 4)
    elif name == "vit_b_16":
        m = models.vit_b_16(weights=None); m.heads.head = nn.Linear(m.heads.head.in_features, 4)
    else:
        raise ValueError(name)
    w = P.Normalized(m)
    w.load_state_dict(ck["state"])
    return w.eval()


def predict(model, arr):
    t = torch.from_numpy(arr.transpose(2, 0, 1).copy()).unsqueeze(0)
    with torch.no_grad():
        p = F.softmax(model(t), 1)[0]
    return int(p.argmax()), float(p.max())


def to_pil(arr):
    return Image.fromarray((np.clip(arr, 0, 1) * 255).round().astype(np.uint8))


def jpeg(q):
    def f(arr):
        b = io.BytesIO(); to_pil(arr).save(b, format="JPEG", quality=q)
        return np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB"), dtype=np.float32) / 255
    return f


def blur(arr):
    return np.asarray(to_pil(arr).filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255


def downup(arr):
    im = to_pil(arr).resize((112, 112), Image.BILINEAR).resize((224, 224), Image.BILINEAR)
    return np.asarray(im, dtype=np.float32) / 255


PURIFIERS = {
    "jpeg75": jpeg(75), "jpeg50": jpeg(50), "median3": lambda a: P._median(a, 3),
    "median5": lambda a: P._median(a, 5), "blur1.0": blur, "down/up": downup,
    "bit3": lambda a: P._bit_depth(a, 3),
}

OTHERS = {}
for n in ("resnet50_s42", "efficientnet_b0_s42", "vit_b_16_s42"):
    p = f"models/{n}.pt"
    if os.path.exists(p):
        OTHERS[n] = load_any(p)
print("Qo'shimcha modellar:", list(OTHERS) or "yo'q")

files = [("TOZA", "Sinov.jpg")] + [(f"PGD {k}/255", f"hujum_rasmlar/hujum_pgd_{k}.png") for k in (4, 8, 16, 32)]
ref = None
for title, path in files:
    arr = P._to_array(Image.open(path))
    c, conf = predict(MAIN, arr)
    if ref is None:
        ref = c
    ok = lambda x: "OK " if x == ref else "XATO"
    print(f"\n===== {title}  (asosiy model: {CLASSES[c]} {conf:.0%} {ok(c)}) =====")
    for name, fn in PURIFIERS.items():
        c2, p2 = predict(MAIN, fn(arr))
        print(f"  tozalash {name:8s} -> {CLASSES[c2]:11s} {p2:4.0%} {ok(c2)}")
    for name, m in OTHERS.items():
        c3, p3 = predict(m, arr)
        print(f"  boshqa model {name:20s} -> {CLASSES[c3]:11s} {p3:4.0%} {ok(c3)}")
print("\n(OK = toza tasvirdagi javob bilan bir xil)")