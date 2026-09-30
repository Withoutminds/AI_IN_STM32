"""Read a USART log or a CubeIDE size dump into baseline/metrics.csv."""

import argparse
import csv
import re
from pathlib import Path


LINE = re.compile(
    r"class=(?P<name>\S+)\s+conf=(?P<conf>[-0-9.]+)\s+infer_ms=(?P<ms>\d+)\s+angle=(?P<angle>\d+)\s+moved=(?P<moved>\d+)"
)
SIZE = re.compile(
    r"^\s*(?P<text>\d+)\s+(?P<data>\d+)\s+(?P<bss>\d+)\s+\d+\s+[0-9a-fA-F]+\s+\S+",
    re.M,
)
REGION = re.compile(
    r"^\s*(?P<name>FLASH|RAM)\s*:\s+(?P<used>\d+)\s+B",
    re.M,
)


def parse_serial(text):
    rows = [match.groupdict() for match in LINE.finditer(text)]
    if not rows:
        raise SystemExit("no class= lines in the serial log")
    infer = [int(row["ms"]) for row in rows]
    moved = sum(int(row["moved"]) for row in rows)
    mean_ms = sum(infer) / len(infer)
    return {
        "frames": len(rows),
        "infer_ms": round(mean_ms, 2),
        "fps": round(1000.0 / mean_ms, 2) if mean_ms else 0,
        "moves": moved,
    }


def parse_memory(text):
    regions = {match.group("name"): int(match.group("used")) for match in REGION.finditer(text)}
    size = SIZE.search(text)
    if "FLASH" in regions or "RAM" in regions:
        return {
            "flash_bytes": regions.get("FLASH", ""),
            "ram_bytes": regions.get("RAM", ""),
        }
    if size:
        text_bytes = int(size.group("text"))
        data_bytes = int(size.group("data"))
        bss_bytes = int(size.group("bss"))
        return {
            "flash_bytes": text_bytes + data_bytes,
            "ram_bytes": data_bytes + bss_bytes,
        }
    raise SystemExit("no size or Memory region lines found")


def update_csv(csv_path, stage, fields):
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []
    found = False
    for row in rows:
        if row["stage"] == stage:
            row.update({key: str(value) for key, value in fields.items()})
            row["source"] = "measured"
            found = True
    if not found:
        raise SystemExit(f"stage {stage} is not in {csv_path}")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", type=Path)
    parser.add_argument("--memory", type=Path)
    parser.add_argument("--stage", default="gesture_int8")
    parser.add_argument("--csv", type=Path, default=Path(__file__).resolve().parents[1] / "baseline" / "metrics.csv")
    args = parser.parse_args()
    fields = {}
    if args.serial:
        serial = parse_serial(args.serial.read_text(encoding="utf-8", errors="replace"))
        fields["infer_ms"] = serial["infer_ms"]
        fields["notes"] = f"frames={serial['frames']} fps={serial['fps']} moves={serial['moves']}"
        print(serial)
    if args.memory:
        memory = parse_memory(args.memory.read_text(encoding="utf-8", errors="replace"))
        fields.update(memory)
        print(memory)
    if not fields:
        raise SystemExit("pass --serial and/or --memory")
    update_csv(args.csv, args.stage, fields)
    print(f"updated {args.csv} stage {args.stage}")


if __name__ == "__main__":
    main()
