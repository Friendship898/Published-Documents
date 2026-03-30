from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SemanticMaskConfig:
    red_center: float = 0.0
    red_width: float = 0.07
    magenta_center: float = 0.90
    magenta_width: float = 0.09
    sat_low: float = 0.28
    sat_high: float = 0.95
    val_low: float = 0.22
    val_high: float = 0.95


def smoothstep(x: np.ndarray, edge0: float, edge1: float) -> np.ndarray:
    t = np.clip((x - edge0) / max(1e-6, edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def circular_hue_distance(h: np.ndarray, center: float) -> np.ndarray:
    d = np.abs(h - center)
    return np.minimum(d, 1.0 - d)


def gaussian_weight(distance: np.ndarray, width: float) -> np.ndarray:
    sigma = max(width, 1e-6)
    return np.exp(-0.5 * (distance / sigma) ** 2)


def build_semantic_weights(
    hsv: np.ndarray,
    alpha: np.ndarray,
    config: SemanticMaskConfig | None = None,
) -> dict[str, np.ndarray | int]:
    cfg = config or SemanticMaskConfig()

    h = hsv[..., 0]
    s = hsv[..., 1]
    v = hsv[..., 2]
    a = alpha.astype(np.float32) / 255.0

    red_hue = gaussian_weight(circular_hue_distance(h, cfg.red_center), cfg.red_width)
    magenta_hue = gaussian_weight(
        circular_hue_distance(h, cfg.magenta_center), cfg.magenta_width
    )

    sat_w = smoothstep(s, cfg.sat_low, cfg.sat_high)
    val_w = smoothstep(v, cfg.val_low, cfg.val_high)
    bright_w = smoothstep(v, 0.50, 1.00)
    dark_w = 1.0 - smoothstep(v, 0.18, 0.55)

    alpha_w = np.power(a, 0.75)

    red_glow = red_hue * sat_w * (0.55 + 0.45 * val_w)
    magenta_link = magenta_hue * sat_w * bright_w * 0.75

    material_suppress = dark_w * (0.45 + 0.55 * red_hue) * (0.5 + 0.5 * sat_w)

    combined = (red_glow + magenta_link) * (1.0 - 0.85 * material_suppress)
    combined = np.clip(combined * alpha_w, 0.0, 1.0)

    red_pixels = int(np.count_nonzero(red_glow > 0.35))
    magenta_pixels = int(np.count_nonzero(magenta_link > 0.30))

    return {
        "combined": combined.astype(np.float32),
        "red_glow": red_glow.astype(np.float32),
        "magenta_link": magenta_link.astype(np.float32),
        "material_suppress": material_suppress.astype(np.float32),
        "red_pixels": red_pixels,
        "magenta_pixels": magenta_pixels,
    }
