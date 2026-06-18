"""Annotate a CCTV clip with REAL YOLO person detection (offline pre-render).

Chạy YOLO (ultralytics, class 0 = person) trên từng frame, vẽ bounding box +
banner "People: N", rồi xuất WebM/VP9. Boxes là output YOLO thật — chỉ render
sẵn để demo mượt (VM chỉ-CPU không phải chạy inference lúc xem). Đây cũng là
pipeline "occupancy bằng CV thật" mô tả trong occupancy_profile ("real-time =
YOLO"): cùng model, chỉ khác là batch offline thay vì stream.

Đây là tool OFFLINE — KHÔNG thêm ultralytics vào image runtime. Chạy trong 1
container có torch + ultralytics (xem lệnh ở cuối / runbook). In ra peak người
phát hiện để set occupancy cho zone tương ứng.

Usage:
  python annotate_cctv_yolo.py --src in.mp4 --out out.webm \
      --start 6 --dur 12 --width 640 --conf 0.35 --model yolo11n.pt
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile

import cv2
from ultralytics import YOLO

BANNER_H = 30


def annotate(src: str, out_webm: str, *, model_name: str = "yolo11n.pt",
             start: float = 0.0, dur: float = 12.0, width: int = 640,
             conf: float = 0.35) -> int:
    model = YOLO(model_name)
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {src}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w0 = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h0 = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    out_w = width
    out_h = int(round(h0 * (width / w0) / 2) * 2)  # even height for vp9
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000.0)

    tmp_mp4 = tempfile.mktemp(suffix=".mp4")
    vw = cv2.VideoWriter(tmp_mp4, cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h))
    max_frames = int(dur * fps)
    peak = 0
    n = 0
    while n < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.resize(frame, (out_w, out_h))
        res = model.predict(frame, classes=[0], conf=conf, verbose=False)[0]
        annotated = res.plot(labels=True, conf=True, line_width=2)
        count = len(res.boxes)
        peak = max(peak, count)
        # top banner with live count
        cv2.rectangle(annotated, (0, 0), (out_w, BANNER_H), (18, 18, 18), -1)
        cv2.putText(annotated, f"YOLO11  |  People: {count}", (10, 21),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (80, 230, 120), 2, cv2.LINE_AA)
        vw.write(annotated)
        n += 1
    cap.release()
    vw.release()

    # mp4v -> WebM/VP9 (broad browser support, license-free; matches other clips)
    subprocess.run(["ffmpeg", "-y", "-i", tmp_mp4, "-c:v", "libvpx-vp9",
                    "-b:v", "0", "-crf", "33", "-an", out_webm],
                   check=True, capture_output=True)
    os.remove(tmp_mp4)
    print(f"{out_webm}: {n} frames, peak people = {peak}")
    return peak


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="yolo11n.pt")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=12.0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.35)
    args = ap.parse_args()
    annotate(args.src, args.out, model_name=args.model, start=args.start,
             dur=args.dur, width=args.width, conf=args.conf)
