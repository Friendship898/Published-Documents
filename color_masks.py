from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SemanticMaskConfig:
    source_hue: float
    highlight_hue_offset: float = -0.10
    source_width: float = 0.07
    highlight_width: float = 0.09
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
    config: SemanticMaskConfig,
) -> dict[str, np.ndarray | int]:
    h = hsv[..., 0]
    s = hsv[..., 1]
    v = hsv[..., 2]
    a = alpha.astype(np.float32) / 255.0

    source_hue = gaussian_weight(
        circular_hue_distance(h, config.source_hue),
        config.source_width,
    )
    highlight_center = (config.source_hue + config.highlight_hue_offset) % 1.0
    highlight_hue = gaussian_weight(
        circular_hue_distance(h, highlight_center),
        config.highlight_width,
    )

    sat_w = smoothstep(s, config.sat_low, config.sat_high)
    val_w = smoothstep(v, config.val_low, config.val_high)
    bright_w = smoothstep(v, 0.50, 1.00)
    dark_w = 1.0 - smoothstep(v, 0.18, 0.55)

    alpha_w = np.power(a, 0.75)

    source_glow = source_hue * sat_w * (0.55 + 0.45 * val_w)
    highlight_link = highlight_hue * sat_w * bright_w * 0.75

    material_suppress = dark_w * (0.45 + 0.55 * source_hue) * (0.5 + 0.5 * sat_w)

    combined = (source_glow + highlight_link) * (1.0 - 0.85 * material_suppress)
    combined = np.clip(combined * alpha_w, 0.0, 1.0)

    source_pixels = int(np.count_nonzero(source_glow > 0.35))
    highlight_pixels = int(np.count_nonzero(highlight_link > 0.30))

    return {
        "combined": combined.astype(np.float32),
        "source_glow": source_glow.astype(np.float32),
        "highlight_link": highlight_link.astype(np.float32),
        "material_suppress": material_suppress.astype(np.float32),
        "source_pixels": source_pixels,
        "highlight_pixels": highlight_pixels,
    }
