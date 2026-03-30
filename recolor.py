from __future__ import annotations

import numpy as np


def hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    color = hex_color.strip().lstrip("#")
    if len(color) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    return tuple(int(color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def blend_hue_circular(h0: np.ndarray, h1: np.ndarray, w: np.ndarray) -> np.ndarray:
    delta = (h1 - h0 + 0.5) % 1.0 - 0.5
    return (h0 + delta * w) % 1.0


def semantic_soft_recolor(
    hsv: np.ndarray,
    combined_w: np.ndarray,
    magenta_link_w: np.ndarray,
    target_hsv: np.ndarray,
    brightness_boost: float = 0.16,
) -> np.ndarray:
    h = hsv[..., 0]
    s = hsv[..., 1]
    v = hsv[..., 2]

    target_h, target_s, target_v = target_hsv

    hue_bias = np.clip(target_h + magenta_link_w * 0.03, 0.0, 1.0)
    h_new = blend_hue_circular(h, hue_bias, np.clip(combined_w * 0.95, 0.0, 1.0))

    sat_mix = 0.20 + 0.25 * combined_w
    s_new = np.clip(s * (1.0 - sat_mix) + target_s * sat_mix, 0.0, 1.0)

    bright_factor = combined_w * (0.55 + 0.45 * np.clip(v, 0.0, 1.0))
    v_lift = brightness_boost * bright_factor
    min_floor = (target_v * 0.50 + 0.22) * np.clip(combined_w, 0.0, 1.0)
    v_new = np.maximum(v + v_lift, np.minimum(1.0, min_floor + v * (1.0 - combined_w * 0.35)))
    v_new = np.clip(v_new, 0.0, 1.0)

    out = np.empty_like(hsv)
    out[..., 0] = h_new
    out[..., 1] = s_new
    out[..., 2] = v_new
    return out
