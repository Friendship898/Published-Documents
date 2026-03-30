from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class HSVThreshold:
    """Thresholds for detecting red pixels in HSV space.

    h is normalized [0, 1). Red wraps around 0, so we use two ranges.
    s and v are normalized [0, 1].
    """

    red_low_1: float = 0.0
    red_high_1: float = 0.04
    red_low_2: float = 0.96
    red_high_2: float = 1.0
    min_s: float = 0.20
    min_v: float = 0.15


@dataclass(frozen=True)
class ProcessResult:
    input_path: Path
    output_path: Path
    status: str
    red_pixels: int = 0
    message: str = ""


def hex_to_rgb01(hex_color: str) -> Tuple[float, float, float]:
    color = hex_color.strip().lstrip("#")
    if len(color) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    r = int(color[0:2], 16) / 255.0
    g = int(color[2:4], 16) / 255.0
    b = int(color[4:6], 16) / 255.0
    return r, g, b


def rgb_to_hsv_np(rgb: np.ndarray) -> np.ndarray:
    """Convert RGB image (float [0,1]) to HSV (float [0,1])."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    cmax = np.max(rgb, axis=-1)
    cmin = np.min(rgb, axis=-1)
    delta = cmax - cmin

    h = np.zeros_like(cmax)
    nonzero = delta > 1e-8

    r_idx = nonzero & (cmax == r)
    g_idx = nonzero & (cmax == g)
    b_idx = nonzero & (cmax == b)

    h[r_idx] = ((g[r_idx] - b[r_idx]) / delta[r_idx]) % 6.0
    h[g_idx] = ((b[g_idx] - r[g_idx]) / delta[g_idx]) + 2.0
    h[b_idx] = ((r[b_idx] - g[b_idx]) / delta[b_idx]) + 4.0
    h = (h / 6.0) % 1.0

    s = np.zeros_like(cmax)
    valid = cmax > 1e-8
    s[valid] = delta[valid] / cmax[valid]

    v = cmax
    return np.stack([h, s, v], axis=-1)


def hsv_to_rgb_np(hsv: np.ndarray) -> np.ndarray:
    """Convert HSV image (float [0,1]) to RGB (float [0,1])."""
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    i = np.floor(h * 6.0).astype(np.int32)
    f = h * 6.0 - i
    i_mod = i % 6

    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)

    rgb = np.empty_like(hsv)

    m0 = i_mod == 0
    m1 = i_mod == 1
    m2 = i_mod == 2
    m3 = i_mod == 3
    m4 = i_mod == 4
    m5 = i_mod == 5

    rgb[m0] = np.stack([v[m0], t[m0], p[m0]], axis=-1)
    rgb[m1] = np.stack([q[m1], v[m1], p[m1]], axis=-1)
    rgb[m2] = np.stack([p[m2], v[m2], t[m2]], axis=-1)
    rgb[m3] = np.stack([p[m3], q[m3], v[m3]], axis=-1)
    rgb[m4] = np.stack([t[m4], p[m4], v[m4]], axis=-1)
    rgb[m5] = np.stack([v[m5], p[m5], q[m5]], axis=-1)

    return rgb


def detect_red_mask(hsv: np.ndarray, threshold: HSVThreshold) -> np.ndarray:
    h = hsv[..., 0]
    s = hsv[..., 1]
    v = hsv[..., 2]

    in_red_range = ((h >= threshold.red_low_1) & (h <= threshold.red_high_1)) | (
        (h >= threshold.red_low_2) & (h <= threshold.red_high_2)
    )
    return in_red_range & (s >= threshold.min_s) & (v >= threshold.min_v)


def recolor_red_to_target(
    rgba: np.ndarray,
    target_color_hex: str,
    threshold: HSVThreshold,
) -> Tuple[np.ndarray, int]:
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    alpha = rgba[..., 3:4]

    hsv = rgb_to_hsv_np(rgb)
    mask = detect_red_mask(hsv, threshold)
    red_pixels = int(np.count_nonzero(mask))

    if red_pixels == 0:
        return rgba, 0

    target_rgb = np.array(hex_to_rgb01(target_color_hex), dtype=np.float32)
    target_h = rgb_to_hsv_np(target_rgb[None, None, :])[0, 0, 0]

    hsv[mask, 0] = target_h
    rgb_new = hsv_to_rgb_np(hsv)
    rgb_uint8 = np.clip(np.round(rgb_new * 255.0), 0, 255).astype(np.uint8)
    out = np.concatenate([rgb_uint8, alpha], axis=-1)
    return out, red_pixels


def process_png(
    input_path: Path,
    output_path: Path,
    target_color_hex: str,
    dry_run: bool = False,
    threshold: HSVThreshold | None = None,
) -> ProcessResult:
    threshold = threshold or HSVThreshold()
    try:
        with Image.open(input_path) as img:
            rgba = np.array(img.convert("RGBA"), dtype=np.uint8)

        out_rgba, red_pixels = recolor_red_to_target(rgba, target_color_hex, threshold)

        if red_pixels == 0:
            return ProcessResult(
                input_path=input_path,
                output_path=output_path,
                status="skipped",
                red_pixels=0,
                message="no red pixels matched",
            )

        if not dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(out_rgba, mode="RGBA").save(output_path, format="PNG")

        return ProcessResult(
            input_path=input_path,
            output_path=output_path,
            status="processed",
            red_pixels=red_pixels,
            message="dry-run" if dry_run else "written",
        )
    except Exception as exc:  # per-file isolation requirement
        return ProcessResult(
            input_path=input_path,
            output_path=output_path,
            status="failed",
            red_pixels=0,
            message=str(exc),
        )
