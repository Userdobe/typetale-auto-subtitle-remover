#!/usr/bin/env python3
"""字字动画输出视频自动去字幕：固定底部字幕区的 OpenCV 内容修复。"""
from __future__ import annotations
import argparse, json, logging, shutil, subprocess, sys, time
from pathlib import Path
import cv2
import numpy as np

DEFAULTS = {
    "output_suffix": "_no_subtitles", "video_extensions": [".mp4", ".mov", ".mkv", ".webm"],
    "subtitle_region": "bottom", "bottom_ratio": 0.28, "mask_padding": 10,
    "inpaint_radius": 3, "inpaint_method": "telea", "poll_seconds": 3,
    "keep_audio": True, "overwrite": False,
}

def load_config(path: Path) -> dict:
    cfg = DEFAULTS.copy()
    if path.exists():
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    return cfg

def build_mask(frame: np.ndarray, cfg: dict) -> np.ndarray:
    h, w = frame.shape[:2]
    ratio = float(cfg.get("bottom_ratio", .28))
    y0 = max(0, int(h * (1 - ratio)))
    roi = frame[y0:h]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # 同时覆盖白/黄等高亮字幕和带描边字幕，避免把整个底部区域全部抹掉。
    bright = cv2.inRange(gray, 150, 255)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, np.array([12, 45, 100]), np.array([45, 255, 255]))
    mask = cv2.bitwise_or(bright, yellow)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 5), np.uint8), iterations=1)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    # 只保留更像字幕的连通区域，避免整片高亮背景被修复。
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    clean = np.zeros_like(mask)
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if area >= max(12, int(w * h * .00001)) and ww >= 3 and hh <= max(100, int(h * .12)):
            clean[labels == i] = 255
    pad = int(cfg.get("mask_padding", 10))
    if pad > 0:
        clean = cv2.dilate(clean, np.ones((max(1, pad // 2), max(1, pad)), np.uint8), iterations=1)
    out = np.zeros((h, w), np.uint8)
    out[y0:h] = clean
    return out

def ffprobe(path: Path) -> tuple[int, int, float, int]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise RuntimeError(f"无法打开视频：{path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return width, height, fps, frames

def process_video(src: Path, dst: Path, cfg: dict) -> None:
    width, height, fps, _ = ffprobe(src)
    temp = dst.with_name(dst.stem + ".__silent__.mp4")
    cap = cv2.VideoCapture(str(src))
    fourcc = cv2.VideoWriter_fourcc(*"avc1")
    writer = cv2.VideoWriter(str(temp), fourcc, fps, (width, height))
    if not writer.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(temp), fourcc, fps, (width, height))
    if not writer.isOpened(): raise RuntimeError("无法创建临时视频，请检查 OpenCV/编码器")
    count = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok: break
            mask = build_mask(frame, cfg)
            method = cv2.INPAINT_NS if str(cfg.get("inpaint_method")).lower() == "ns" else cv2.INPAINT_TELEA
            fixed = cv2.inpaint(frame, mask, float(cfg.get("inpaint_radius", 3)), method)
            writer.write(fixed)
            count += 1
            if count % 100 == 0: logging.info("%s: 已处理 %d 帧", src.name, count)
    finally:
        cap.release(); writer.release()
    if not shutil.which("ffmpeg"):
        raise RuntimeError("未找到 ffmpeg。请安装 FFmpeg 并将 ffmpeg.exe 加入 PATH")
    cmd = ["ffmpeg", "-y", "-i", str(temp)]
    if cfg.get("keep_audio", True): cmd += ["-i", str(src), "-map", "0:v:0", "-map", "1:a?", "-c:v", "copy", "-c:a", "aac", "-shortest"]
    else: cmd += ["-c", "copy"]
    cmd += [str(dst)]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    temp.unlink(missing_ok=True)
    logging.info("完成：%s", dst)

def output_path(src: Path, cfg: dict) -> Path:
    return src.with_name(src.stem + str(cfg.get("output_suffix", "_no_subtitles")) + ".mp4")

def process_once(src: Path, cfg: dict) -> Path:
    dst = output_path(src, cfg)
    if dst.exists() and not cfg.get("overwrite", False): return dst
    process_video(src, dst, cfg)
    return dst

def watch(folder: Path, cfg: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    done: set[Path] = set()
    exts = {x.lower() for x in cfg.get("video_extensions", DEFAULTS["video_extensions"])}
    logging.info("监视目录：%s", folder)
    while True:
        for src in sorted(folder.iterdir()):
            if not src.is_file() or src.suffix.lower() not in exts or str(cfg.get("output_suffix")) in src.stem: continue
            if src in done: continue
            try:
                size1 = src.stat().st_size; time.sleep(0.5); size2 = src.stat().st_size
                if size1 != size2 or size2 < 1024: continue
                process_once(src, cfg); done.add(src)
            except Exception as exc: logging.exception("处理失败 %s：%s", src, exc); done.add(src)
        time.sleep(float(cfg.get("poll_seconds", 3)))

def main() -> int:
    ap = argparse.ArgumentParser(description="字字动画输出视频自动去字幕")
    ap.add_argument("--config", default="config.json"); ap.add_argument("--input", help="单个视频路径；不填则监视 watch_dir")
    ap.add_argument("--watch-dir", help="覆盖配置中的监视目录")
    args = ap.parse_args(); logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(Path(args.config))
    if args.input: process_once(Path(args.input).resolve(), cfg); return 0
    folder = Path(args.watch_dir or cfg.get("watch_dir", Path.cwd() / "outputs")).expanduser()
    watch(folder, cfg); return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except KeyboardInterrupt: print("\n已停止监视")
    except Exception as exc: logging.error("错误：%s", exc); raise SystemExit(1)
