"""Roda no venv do MuseTalk (tem OpenCV). Escolhe o trecho mais estável do vídeo base:
rosto inteiro, centralizado, de tamanho constante e com pouco movimento de câmera.
Uso: python _pick_segment.py <video> <segundos>  ->  imprime JSON na última linha."""
import json
import sys

import cv2
import numpy as np

SAMPLES_PER_SEC = 4
STABLE = 0.5  # pontuação máxima para considerar o trecho estável (menor = mais estável)


def analyse(path, window_s):
    """Tenta a janela pedida e, se o vídeo não tiver um trecho estável tão longo, janelas menores."""
    rows = _scan(path)
    w, longest = window_s, None
    while w >= 4:
        res = _best_window(rows, w)
        if res:
            res["window_s"] = w
            if res["score"] <= STABLE:  # estável de verdade: aceita
                return res
            longest = longest or res
        w /= 2
    return longest or {"start": 0.0, "found": False, "samples": len(rows)}


def _scan(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, round(fps / SAMPLES_PER_SEC))
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    rows, prev, i = [], None, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            h0, w0 = frame.shape[:2]
            g = cv2.cvtColor(cv2.resize(frame, (320, int(320 * h0 / w0))), cv2.COLOR_BGR2GRAY)
            h, w = g.shape
            faces = det.detectMultiScale(g, 1.1, 5, minSize=(int(w * 0.08), int(w * 0.08)))
            small = cv2.resize(g, (64, 64)).astype(np.float32)
            motion = float(np.abs(small - prev).mean()) if prev is not None else 0.0
            prev = small
            if len(faces):
                x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                edge = x < 0.03 * w or x + fw > 0.97 * w or y < 0.01 * h
                rows.append((True, (x + fw / 2) / w, (y + fh / 2) / h, fw / w, edge, motion))
            else:
                rows.append((False, 0, 0, 0, False, motion))
        i += 1
    cap.release()
    return rows


def _best_window(rows, window_s):
    n = len(rows)
    win = int(window_s * SAMPLES_PER_SEC)
    if win < 2 or n < win:
        return None
    best = None
    for s in range(0, n - win + 1):
        seg = rows[s:s + win]
        found = [r for r in seg if r[0]]
        rate = len(found) / win
        if rate < 0.9 or any(r[4] for r in found):
            continue
        cx, cy, sz = (np.array([r[k] for r in found]) for k in (1, 2, 3))
        score = (cx.std() + cy.std()) * 4 + sz.std() / max(sz.mean(), 1e-6) * 2 \
            + np.mean([r[5] for r in seg]) / 50 + abs(cx.mean() - 0.5)
        if best is None or score < best[0]:
            best = (score, s, float(np.median(sz)), rate)
    if best is None:
        return None
    return {"start": round(best[1] / SAMPLES_PER_SEC, 2), "found": True, "score": round(float(best[0]), 3),
            "face_width_ratio": round(best[2], 3), "samples": n}


if __name__ == "__main__":
    print(json.dumps(analyse(sys.argv[1], float(sys.argv[2]))))
