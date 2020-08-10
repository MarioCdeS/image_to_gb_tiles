from __future__ import annotations

import argparse
import sys
from typing import Generator, List, Optional, Tuple, TypeVar

from PIL import Image, UnidentifiedImageError


T = TypeVar("T")
Palette = Tuple[int, int, int, int]
Thresholds = Tuple[int, int, int]


DEFAULT_OUTPUT: str = "output.bin"
DEFAULT_PALETTE: Palette = (0, 1, 2, 3)
DEFAULT_THRESHOLDS: Thresholds = (63, 127, 191)


class ImageError(Exception):
    pass


def main() -> None:
    args = parse_arguments()
    palette = tuple(args.palette) if args.palette else None
    thresholds = tuple(args.thresholds) if args.thresholds else None

    try:
        image = load_image_as_grayscale(args.image)
        binary = convert_grayscale_to_binary(image, palette, thresholds)
    except ImageError as err:
        print(err, file=sys.stderr)
        sys.exit(1)

    try:
        write_binary_to_file(args.output, binary)
    except IOError as err:
        print(f"Unable to output binary file: {err}", file=sys.stderr)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="path of the image file to convert")
    parser.add_argument(
        "-o", "--output", help="path to output Game Boy binary to"
    )
    parser.add_argument(
        "-p",
        "--palette",
        nargs=4,
        type=int,
        metavar="I",
        help="grayscale palette values (0-3)",
    )
    parser.add_argument(
        "-t",
        "--thresholds",
        nargs=3,
        type=int,
        metavar="U8",
        help="grayscale threshold values",
    )

    return parser.parse_args()


def load_image_as_grayscale(image_path: str) -> Image:
    try:
        image = Image.open(image_path)
    except FileNotFoundError as err:
        raise ImageError(f"Image file '{image_path}' does not exist.") from err
    except UnidentifiedImageError as err:
        raise ImageError(f"'{image_path}' is not a valid image file.") from err

    if image.mode != "L":
        image = image.convert("L")

    return image


def convert_grayscale_to_binary(
    image: Image,
    palette: Optional[Palette] = None,
    thresholds: Optional[Thresholds] = None,
) -> bytes:
    assert image.mode == "L", "Image argument must contain a grayscale image."

    palette = palette or DEFAULT_PALETTE
    thresholds = thresholds or DEFAULT_THRESHOLDS

    width, height = image.size

    if width % 8 or height % 8:
        raise ImageError(
            f"The dimensions of '{image.filename}' are not a multiple of 8."
        )

    pixels = image.load()
    palette_values = [
        [
            grayscale_to_palette(pixels[i, j], palette, thresholds)
            for i in range(width)
        ]
        for j in range(height)
    ]

    binary = []

    for tile in grid_8x8_segments(palette_values):
        tile_bytes = []

        for row in tile:
            row_byte1 = 0
            row_byte2 = 0

            for value in row:
                row_byte1 = (row_byte1 << 1) | (1 if value & 1 else 0)
                row_byte2 = (row_byte2 << 1) | (1 if value & 2 else 0)

            tile_bytes.append(row_byte1)
            tile_bytes.append(row_byte2)

        binary.extend(tile_bytes)

    return bytes(binary)


def grayscale_to_palette(
    value: int, palette: Palette, thresholds: Thresholds
) -> int:
    low, mid, high = thresholds

    if value <= low:
        return palette[0]
    elif value <= mid:
        return palette[1]
    elif value <= high:
        return palette[2]
    else:
        return palette[3]


def grid_8x8_segments(
    grid: List[List[T]],
) -> Generator[List[List[T]], None, None]:
    height = len(grid)
    assert (
        height > 0 and not height % 8
    ), "Grid height must be a multiple of 8."

    width = len(grid[0])
    assert width > 0 and not width % 8, "Grid width must be a multiple of 8."

    for j in range(0, height, 8):
        for i in range(0, width, 8):
            segment = [
                [grid[y][x] for x in range(i, i + 8)] for y in range(j, j + 8)
            ]
            yield segment


def write_binary_to_file(output_path: Optional[str], binary: bytes) -> None:
    output_path = output_path or DEFAULT_OUTPUT

    with open(output_path, "wb") as out:
        out.write(binary)


if __name__ == "__main__":
    main()
