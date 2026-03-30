from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from color_similarity import signed_hue_delta


@dataclass(frozen=True)
class PaletteBandRemapConfig:
    highlight_follow_strength: float = 0.70
    shadow_follow_strength: float = 0.55
    material_protect_strength: float = 0.60
    brightness_compensation: float = 0.18
    saturation_compensation: float = 0.12


def blend_hue_circular(h0: np.ndarray, h1: np.ndarray, w: np.ndarray) -> np.ndarray:
    delta = signed_hue_delta(h0, h1)
    return (h0 + delta * w) % 1.0


def circular_weighted_mean(hues: list[np.ndarray], weights: list[np.ndarray]) -> np.ndarray:
    sin_sum = np.zeros_like(hues[0], dtype=np.float32)
    cos_sum = np.zeros_like(hues[0], dtype=np.float32)
    for hue, weight in zip(hues, weights, strict=True):
        radians = hue * (2.0 * np.pi)
        sin_sum += np.sin(radians) * weight
        cos_sum += np.cos(radians) * weight
    angle = np.arctan2(sin_sum, cos_sum)
    return (angle / (2.0 * np.pi)) % 1.0


def palette_band_remap(
    hsv: np.ndarray,
    source_hsv: np.ndarray,
    target_hsv: np.ndarray,
    masks: dict[str, np.ndarray | int],
    config: PaletteBandRemapConfig,
) -> np.ndarray:
    h = hsv[..., 0]
    s = hsv[..., 1]
    v = hsv[..., 2]

    source_h, source_s, source_v = [float(x) for x in source_hsv]
    target_h, target_s, target_v = [float(x) for x in target_hsv]

    main_w = np.asarray(masks["source"], dtype=np.float32)
    highlight_w = np.asarray(masks["highlight"], dtype=np.float32)
    shadow_w = np.asarray(masks["shadow"], dtype=np.float32)
    protect_w = np.asarray(masks["material_protect"], dtype=np.float32)
    combined_w = np.asarray(masks["combined"], dtype=np.float32)

    relative_hue = signed_hue_delta(source_h, h)
    main_target_h = (target_h + relative_hue * 0.85) % 1.0
    highlight_target_h = (target_h + relative_hue * 0.95 + 0.02 * np.clip(config.highlight_follow_strength, 0.0, 1.5)) % 1.0
    shadow_target_h = (target_h + relative_hue * 0.60 - 0.015 * np.clip(config.shadow_follow_strength, 0.0, 1.5)) % 1.0
    desired_h = circular_weighted_mean(
        [main_target_h, highlight_target_h, shadow_target_h],
        [
            0.65 + main_w,
            0.15 + highlight_w * np.clip(config.highlight_follow_strength, 0.0, 1.5),
            0.15 + shadow_w * np.clip(config.shadow_follow_strength, 0.0, 1.5),
        ],
    )
    h_new = blend_hue_circular(h, desired_h, np.clip(combined_w * 0.98, 0.0, 1.0))

    sat_anchor = np.clip(target_s + (s - source_s) * 0.85, 0.0, 1.0)
    sat_mix = np.clip(combined_w * (0.70 + np.clip(config.saturation_compensation, 0.0, 1.0)), 0.0, 1.0)
    sat_comp = (target_s - source_s) * np.clip(config.saturation_compensation, -1.0, 1.0)
    sat_detail = highlight_w * 0.06 - shadow_w * 0.04 - protect_w * 0.05 * np.clip(config.material_protect_strength, 0.0, 1.5)
    s_target = np.clip(sat_anchor + sat_comp * combined_w + sat_detail, 0.0, 1.0)
    s_new = np.clip(s * (1.0 - sat_mix) + s_target * sat_mix, 0.0, 1.0)

    value_anchor = np.clip(target_v + (v - source_v) * 0.92, 0.0, 1.0)
    bright_delta = (target_v - source_v) * np.clip(config.brightness_compensation, -1.0, 1.0)
    highlight_boost = highlight_w * np.clip(config.highlight_follow_strength, 0.0, 1.5) * (0.06 + max(0.0, target_v - source_v) * 0.14)
    shadow_lift = shadow_w * np.clip(config.shadow_follow_strength, 0.0, 1.5) * max(0.0, target_v - source_v) * 0.10
    shadow_guard = shadow_w * np.clip(config.shadow_follow_strength, 0.0, 1.5) * max(0.0, source_v - target_v) * 0.12
    material_guard = protect_w * np.clip(config.material_protect_strength, 0.0, 1.5) * 0.08
    v_target = np.clip(value_anchor + combined_w * bright_delta + highlight_boost + shadow_lift - shadow_guard - material_guard, 0.0, 1.0)
    v_new = np.clip(v * (1.0 - combined_w * 0.12) + v_target * (combined_w * 0.12 + combined_w * 0.88), 0.0, 1.0)

    out = np.empty_like(hsv)
    out[..., 0] = h_new
    out[..., 1] = s_new
    out[..., 2] = v_new
    return out
