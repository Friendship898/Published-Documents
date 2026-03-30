from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from color_masks import build_semantic_weights
from recolor import hex_to_rgb01, semantic_soft_recolor


@dataclass(frozen=True)
class ProcessResult:
    input_path: Path
    output_path: Path
    status: str
    red_pixels: int = 0
    magenta_pixels: int = 0
    message: str = ""


def rgb_to_hsv_np(rgb: np.ndarray) -> np.ndarray:
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


def recolor_image_semantic(
    rgba: np.ndarray,
    target_color_hex: str,
) -> tuple[np.ndarray, int, int, np.ndarray]:
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    alpha = rgba[..., 3:4]

    hsv = rgb_to_hsv_np(rgb)
    masks = build_semantic_weights(hsv, alpha[..., 0])
    combined_w = masks["combined"]

    target_rgb = np.array(hex_to_rgb01(target_color_hex), dtype=np.float32)
    target_hsv = rgb_to_hsv_np(target_rgb[None, None, :])[0, 0, :]

    mapped_hsv = semantic_soft_recolor(
        hsv=hsv,
        combined_w=combined_w,
        magenta_link_w=masks["magenta_link"],
        target_hsv=target_hsv,
    )
    mapped_rgb = hsv_to_rgb_np(mapped_hsv)

    w = combined_w[..., None]
    rgb_blend = rgb * (1.0 - w) + mapped_rgb * w
    rgb_uint8 = np.clip(np.round(rgb_blend * 255.0), 0, 255).astype(np.uint8)

    out = np.concatenate([rgb_uint8, alpha], axis=-1)
    return out, int(masks["red_pixels"]), int(masks["magenta_pixels"]), combined_w


def save_weight_mask(path: Path, weight: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = np.clip(np.round(weight * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(mask, mode="L").save(path, format="PNG")


def process_png(
    input_path: Path,
    output_path: Path,
    target_color_hex: str,
    dry_run: bool = False,
    mode: str = "semantic_soft_recolor",
    mask_output_path: Path | None = None,
) -> ProcessResult:
    try:
        with Image.open(input_path) as img:
            rgba = np.array(img.convert("RGBA"), dtype=np.uint8)

        if mode != "semantic_soft_recolor":
            raise ValueError(f"Unsupported mode: {mode}")

        out_rgba, red_pixels, magenta_pixels, weight = recolor_image_semantic(
            rgba, target_color_hex
        )

        if red_pixels == 0 and magenta_pixels == 0:
            return ProcessResult(
                input_path=input_path,
                output_path=output_path,
                status="skipped",
                red_pixels=0,
                magenta_pixels=0,
                message="no semantic red/magenta highlights matched",
            )

        if not dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(out_rgba, mode="RGBA").save(output_path, format="PNG")
            if mask_output_path is not None:
                save_weight_mask(mask_output_path, weight)

        return ProcessResult(
            input_path=input_path,
            output_path=output_path,
            status="processed",
            red_pixels=red_pixels,
            magenta_pixels=magenta_pixels,
            message="dry-run" if dry_run else "written",
        )
    except Exception as exc:
        return ProcessResult(
            input_path=input_path,
            output_path=output_path,
            status="failed",
            red_pixels=0,
            magenta_pixels=0,
            message=str(exc),
        )
