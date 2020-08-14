from __future__ import annotations

import argparse
import sys
from typing import Generator, List, Tuple, TypeVar

from PIL import Image, UnidentifiedImageError


T = TypeVar("T")
Palette = Tuple[int, int, int, int]
Thresholds = Tuple[int, int, int]

MAX_GB_TILES: int = 255

DEFAULT_TILESET_FILE: str = "tile-set.bin"
DEFAULT_INDICES_FILE: str = "indices.bin"
DEFAULT_PALETTE: Palette = (0, 1, 2, 3)
DEFAULT_THRESHOLDS: Thresholds = (63, 127, 191)


class ImageError(Exception):
    pass


def main() -> None:
    args = parse_arguments()

    try:
        image = load_image_as_grayscale(args.image)
        tile_set, indices = convert_grayscale_to_tile_set(
            image, args.palette, args.thresholds
        )
    except ImageError as err:
        print(err, file=sys.stderr)
        sys.exit(1)

    print(f"{len(tile_set)} unique tiles found.")

    if len(tile_set) > MAX_GB_TILES:
        print(
            "Warning: The total size of this tile-set exceeds the allocated "
            "VRAM size for tiles.",
            file=sys.stderr,
        )

    try:
        write_tile_set_to_file(args.output, tile_set)
        write_indices_to_file(args.indices, indices)
    except IOError as err:
        print(f"Failed to generate output binaries: {err}", file=sys.stderr)
    else:
        print(f"Tile-set outputted to '{args.output}'.")
        print(f"Indices outputted to '{args.indices}'.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="path of the image file to convert")
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_TILESET_FILE,
        help="output path for the tile-set binary",
    )
    parser.add_argument(
        "-i",
        "--indices",
        default=DEFAULT_INDICES_FILE,
        help="output path for the tile-set indices binary",
    )
    parser.add_argument(
        "-p",
        "--palette",
        nargs=4,
        type=int,
        metavar="I",
        default=DEFAULT_PALETTE,
        help="grayscale palette values (0-3)",
    )
    parser.add_argument(
        "-t",
        "--thresholds",
        nargs=3,
        type=int,
        metavar="U8",
        default=DEFAULT_THRESHOLDS,
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


def convert_grayscale_to_tile_set(
    image: Image, palette: Palette, thresholds: Thresholds
) -> Tuple[List[bytes], List[int]]:
    assert image.mode == "L", "Image argument must contain a grayscale image."

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

    tile_set = []

    for tile in grid_8x8_segments(palette_values):
        tile_bytes = []

        for row in tile:
            row_byte1 = 0
            row_byte2 = 0

            for value in row:
                row_byte1 = (row_byte1 << 1) | (value & 1)
                row_byte2 = (row_byte2 << 1) | ((value & 2) >> 1)

            tile_bytes.append(row_byte1)
            tile_bytes.append(row_byte2)

        tile_set.append(bytes(tile_bytes))

    return reduce_tile_set(tile_set)


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


def reduce_tile_set(tile_set: List[bytes]) -> Tuple[List[bytes], List[int]]:
    reduced_set = list(set(tile_set))
    index_lookup = {tile: i for i, tile in enumerate(reduced_set)}
    indices = [index_lookup[tile] for tile in tile_set]
    return reduced_set, indices


def write_tile_set_to_file(file_path: str, tile_set: List[bytes]) -> None:
    with open(file_path, "wb") as out:
        for tile in tile_set:
            out.write(tile)


def write_indices_to_file(file_path: str, indices: List[int]) -> None:
    with open(file_path, "wb") as out:
        out.write(bytes(indices))


if __name__ == "__main__":
    main()
