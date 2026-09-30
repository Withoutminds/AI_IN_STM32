"""Draw a separable stand-in set so the export path can be checked without a camera."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

CLASSES = ("left", "up", "stop", "down", "right")


def render(name, rng):
    image = Image.new("RGB", (160, 160), (36, 36, 36))
    draw = ImageDraw.Draw(image)
    j = int(rng.integers(-8, 9))
    color = (230, 210, 60)
    if name == "left":
        draw.polygon([(110 + j, 50), (40 + j, 80), (110 + j, 110)], fill=color)
    elif name == "right":
        draw.polygon([(50 + j, 50), (120 + j, 80), (50 + j, 110)], fill=color)
    elif name == "up":
        draw.polygon([(50, 110 + j), (80, 40 + j), (110, 110 + j)], fill=color)
    elif name == "down":
        draw.polygon([(50, 50 + j), (80, 120 + j), (110, 50 + j)], fill=color)
    else:
        draw.ellipse((48 + j, 48, 112 + j, 112), fill=(200, 50, 50))
    crop = 16 + int(rng.integers(0, 8))
    image = image.crop((crop, crop, crop + 128, crop + 128))
    pixels = np.asarray(image, dtype=np.int16)
    pixels += rng.integers(-14, 15, size=pixels.shape, dtype=np.int16)
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))


def write_split(root, split, count, seed):
    rng = np.random.default_rng(seed)
    for name in CLASSES:
        folder = root / split / name
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(count):
            render(name, rng).save(folder / f"{name}_{index:03d}.jpg", quality=90)


def write_outliers(root, folder_name, count, seed):
    rng = np.random.default_rng(seed)
    folder = root / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        if index % 2 == 0:
            pixels = rng.integers(0, 256, size=(128, 128, 3), dtype=np.uint8)
        else:
            level = int(rng.integers(12, 70))
            pixels = np.full((128, 128, 3), level, dtype=np.int16)
            pixels += rng.integers(-8, 9, size=pixels.shape, dtype=np.int16)
            pixels = np.clip(pixels, 0, 255).astype(np.uint8)
        Image.fromarray(pixels).save(folder / f"outlier_{index:03d}.jpg", quality=90)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--train", type=int, default=48)
    parser.add_argument("--val", type=int, default=12)
    parser.add_argument("--test", type=int, default=16)
    parser.add_argument("--outlier", type=int, default=48)
    parser.add_argument("--unknown", type=int, default=32)
    args = parser.parse_args()
    write_split(args.out, "train", args.train, 11)
    write_split(args.out, "val", args.val, 29)
    write_split(args.out, "test", args.test, 47)
    write_outliers(args.out, "outlier", args.outlier, 71)
    write_outliers(args.out, "unknown", args.unknown, 97)
    (args.out / "SYNTHETIC.txt").write_text(
        "Pipeline check only. Replace these folders with real gesture photos before the thesis numbers.\n",
        encoding="utf-8",
    )
    print(f"wrote synthetic images under {args.out}")


if __name__ == "__main__":
    main()
