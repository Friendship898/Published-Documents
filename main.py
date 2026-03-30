from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from processor import ProcessResult, process_image


LOGGER = logging.getLogger("png-red-to-orange")


@dataclass
class BatchSummary:
    total: int
    processed: int
    skipped: int
    failed: int


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Semantic PNG recolor with soft masks and brightness compensation."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input directory")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--source-color", default="#FF0000", help="Source hex color (default: red)")
    parser.add_argument("--target-color", default="#FF8A00", help="Target hex color (default: orange)")
    parser.add_argument("--mode", default="semantic_soft_recolor", choices=["semantic_soft_recolor"])
    parser.add_argument("--recursive", action="store_true", default=True, help="Recursively scan input")
    parser.add_argument("--no-recursive", dest="recursive", action="store_false")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, do not write final outputs")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads")
    parser.add_argument("--preview", nargs="?", const=5, default=0, type=int, help="Generate N before/after previews")
    parser.add_argument("--preview-mask", action="store_true", help="Also save semantic weight masks")
    parser.add_argument("--max-files", type=int, default=0, help="Only process first N files (0=all)")
    return parser.parse_args()


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}


def find_images(input_dir: Path, recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    return sorted([p for p in input_dir.glob(pattern) if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS])


def format_log(result: ProcessResult) -> str:
    return (
        f"file={result.input_path} status={result.status} source_pixels={result.source_pixels} "
        f"highlight_pixels={result.highlight_pixels} output={result.output_path} message={result.message}"
    )


def save_preview(before_path: Path, after_path: Path, preview_path: Path) -> None:
    with Image.open(before_path).convert("RGBA") as before, Image.open(after_path).convert("RGBA") as after:
        canvas = Image.new("RGBA", (before.width + after.width, max(before.height, after.height)), (0, 0, 0, 0))
        canvas.paste(before, (0, 0))
        canvas.paste(after, (before.width, 0))
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(preview_path, format="PNG")


def run_batch(
    input_dir: Path,
    output_dir: Path,
    source_color: str,
    target_color: str,
    mode: str,
    recursive: bool,
    dry_run: bool,
    workers: int,
    preview_count: int,
    preview_mask: bool,
    max_files: int,
    on_result: Callable[[ProcessResult], None] | None = None,
) -> BatchSummary:
    png_files = find_images(input_dir, recursive)
    if max_files > 0:
        png_files = png_files[:max_files]

    processed = skipped = failed = 0
    futures = []
    processed_outputs: list[tuple[Path, Path, Path]] = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        for in_path in png_files:
            rel = in_path.relative_to(input_dir)
            out_path = output_dir / rel
            mask_path = (output_dir / "_mask_preview" / rel) if preview_mask else None
            futures.append(
                executor.submit(
                    process_image,
                    input_path=in_path,
                    output_path=out_path,
                    source_color_hex=source_color,
                    target_color_hex=target_color,
                    dry_run=dry_run,
                    mode=mode,
                    mask_output_path=mask_path,
                )
            )

        for fut in as_completed(futures):
            result = fut.result()
            if on_result is not None:
                on_result(result)
            if result.status == "processed":
                processed += 1
                if not dry_run:
                    rel = result.input_path.relative_to(input_dir)
                    processed_outputs.append((result.input_path, result.output_path, rel))
            elif result.status == "skipped":
                skipped += 1
            else:
                failed += 1

    if preview_count > 0 and not dry_run:
        for before_path, after_path, rel in processed_outputs[:preview_count]:
            preview_path = output_dir / "_preview" / rel
            save_preview(before_path, after_path, preview_path)

    return BatchSummary(total=len(png_files), processed=processed, skipped=skipped, failed=failed)


def main() -> int:
    args = parse_args()
    setup_logging()

    if not args.input.exists() or not args.input.is_dir():
        LOGGER.error("Input directory not found: %s", args.input)
        return 2

    png_files = find_images(args.input, args.recursive)
    if args.max_files > 0:
        png_files = png_files[: args.max_files]

    if not png_files:
        LOGGER.warning("No PNG/JPG files found in %s", args.input)
        return 0

    LOGGER.info(
        "Found %d image files | mode=%s source=%s target=%s recursive=%s dry_run=%s workers=%d preview=%s max_files=%d",
        len(png_files),
        args.mode,
        args.source_color,
        args.target_color,
        args.recursive,
        args.dry_run,
        args.workers,
        args.preview,
        args.max_files,
    )

    def log_result(result: ProcessResult) -> None:
        if result.status == "failed":
            LOGGER.error(format_log(result))
        else:
            LOGGER.info(format_log(result))

    summary = run_batch(
        input_dir=args.input,
        output_dir=args.output,
        source_color=args.source_color,
        target_color=args.target_color,
        mode=args.mode,
        recursive=args.recursive,
        dry_run=args.dry_run,
        workers=args.workers,
        preview_count=max(0, args.preview),
        preview_mask=args.preview_mask,
        max_files=max(0, args.max_files),
        on_result=log_result,
    )

    LOGGER.info(
        "Done | total=%d processed=%d skipped=%d failed=%d",
        summary.total,
        summary.processed,
        summary.skipped,
        summary.failed,
    )
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
