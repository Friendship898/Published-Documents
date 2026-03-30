from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from processor import ProcessResult, process_png


LOGGER = logging.getLogger("png-red-to-orange")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch recolor red regions in PNG images to a target color using HSV hue mapping."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input directory")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument(
        "--target-color",
        default="#FF8A00",
        help="Target hex color, e.g. #FF8A00",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Recursively scan input directory (default: enabled)",
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Disable recursive scan and only process top-level PNG files",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Detect only, do not write output files"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker threads",
    )
    return parser.parse_args()


def find_pngs(input_dir: Path, recursive: bool) -> list[Path]:
    pattern = "**/*.png" if recursive else "*.png"
    return sorted([p for p in input_dir.glob(pattern) if p.is_file()])


def format_log(result: ProcessResult) -> str:
    return (
        f"file={result.input_path} status={result.status} red_pixels={result.red_pixels} "
        f"output={result.output_path} message={result.message}"
    )


def main() -> int:
    args = parse_args()
    setup_logging()

    if not args.input.exists() or not args.input.is_dir():
        LOGGER.error("Input directory not found: %s", args.input)
        return 2

    png_files = find_pngs(args.input, args.recursive)
    if not png_files:
        LOGGER.warning("No PNG files found in %s", args.input)
        return 0

    LOGGER.info(
        "Found %d PNG files | recursive=%s | dry_run=%s | workers=%d",
        len(png_files),
        args.recursive,
        args.dry_run,
        args.workers,
    )

    processed = skipped = failed = 0
    futures = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        for in_path in png_files:
            rel = in_path.relative_to(args.input)
            out_path = args.output / rel
            futures.append(
                executor.submit(
                    process_png,
                    input_path=in_path,
                    output_path=out_path,
                    target_color_hex=args.target_color,
                    dry_run=args.dry_run,
                )
            )

        for fut in as_completed(futures):
            result = fut.result()
            if result.status == "processed":
                processed += 1
                LOGGER.info(format_log(result))
            elif result.status == "skipped":
                skipped += 1
                LOGGER.info(format_log(result))
            else:
                failed += 1
                LOGGER.error(format_log(result))

    LOGGER.info(
        "Done | total=%d processed=%d skipped=%d failed=%d",
        len(png_files),
        processed,
        skipped,
        failed,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
