"""Train MobileNetV2 alpha 0.35 at 128x128 and write FP32 and INT8 TFLite files."""

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image

from evaluate import write_report

ROOT = Path(__file__).resolve().parent
LABELS = ROOT.parent / "deploy" / "gesture_labels.txt"
INPUT = 128


def class_names():
    names = [line.strip() for line in LABELS.read_text(encoding="utf-8").splitlines() if line.strip()]
    if names != ["left", "up", "stop", "down", "right"]:
        raise SystemExit(f"unexpected labels in {LABELS}: {names}")
    return names


def load_outlier(folder):
    images = []
    for path in sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.png")):
        image = Image.open(path).convert("RGB").resize((INPUT, INPUT))
        images.append(np.asarray(image, dtype=np.float32))
    if not images:
        raise SystemExit(f"no images in {folder}")
    return np.stack(images)


def load_split(root, names):
    images = []
    labels = []
    for index, name in enumerate(names):
        folder = root / name
        paths = sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.png"))
        if not paths:
            raise SystemExit(f"no images in {folder}")
        for path in paths:
            image = Image.open(path).convert("RGB").resize((INPUT, INPUT))
            images.append(np.asarray(image, dtype=np.float32))
            labels.append(index)
    return np.stack(images), np.asarray(labels, dtype=np.int32)


def build(num_classes, weights):
    inputs = tf.keras.Input(shape=(INPUT, INPUT, 3), name="image")
    scaled = tf.keras.layers.Rescaling(1.0 / 127.5, offset=-1.0, name="rescale")(inputs)
    base = tf.keras.applications.MobileNetV2(
        alpha=0.35,
        include_top=False,
        weights=weights,
        input_tensor=scaled,
        pooling="avg",
    )
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax", name="probs")(base.output)
    model = tf.keras.Model(inputs, outputs, name="gesture_mobilenetv2_a035_128")
    if weights is None:
        # Default BatchNorm momentum is 0.99, so a short from-scratch run
        # never updates the moving statistics used at evaluation time.
        for layer in base.layers:
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                layer.momentum = 0.9
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def export_tflite(model, train_images, out_dir):
    fp32_converter = tf.lite.TFLiteConverter.from_keras_model(model)
    fp32_bytes = fp32_converter.convert()
    fp32_path = out_dir / "gesture_fp32.tflite"
    fp32_path.write_bytes(fp32_bytes)

    def representative():
        count = min(100, len(train_images))
        for index in range(count):
            yield [train_images[index : index + 1]]

    int8_converter = tf.lite.TFLiteConverter.from_keras_model(model)
    int8_converter.optimizations = [tf.lite.Optimize.DEFAULT]
    int8_converter.representative_dataset = representative
    int8_converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    int8_converter.inference_input_type = tf.int8
    int8_converter.inference_output_type = tf.float32
    int8_bytes = int8_converter.convert()
    int8_path = out_dir / "gesture_int8.tflite"
    int8_path.write_bytes(int8_bytes)
    return fp32_path, int8_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--weights", choices=("none", "imagenet"), default="none")
    args = parser.parse_args()

    names = class_names()
    train_x, train_y = load_split(args.data / "train", names)
    val_x, val_y = load_split(args.data / "val", names)
    train_target = tf.keras.utils.to_categorical(train_y, len(names))
    val_target = tf.keras.utils.to_categorical(val_y, len(names))
    outlier_dir = args.data / "outlier"
    if outlier_dir.is_dir() and any(outlier_dir.glob("*.jpg")):
        outlier_x = load_outlier(outlier_dir)
        outlier_target = np.full((len(outlier_x), len(names)), 1.0 / len(names), dtype=np.float32)
        train_x = np.concatenate([train_x, outlier_x])
        train_target = np.concatenate([train_target, outlier_target])
    weights = None if args.weights == "none" else "imagenet"
    model = build(len(names), weights)
    history = model.fit(
        train_x,
        train_target,
        validation_data=(val_x, val_target),
        epochs=args.epochs,
        batch_size=args.batch_size,
        verbose=2,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    model.save(args.out / "gesture.keras")
    fp32_path, int8_path = export_tflite(model, train_x, args.out)
    summary = {
        "labels": names,
        "input": [INPUT, INPUT, 3],
        "weights": args.weights,
        "epochs": args.epochs,
        "parameters": int(model.count_params()),
        "final_val_accuracy": float(history.history["val_accuracy"][-1]),
        "fp32_tflite": str(fp32_path),
        "int8_tflite": str(int8_path),
        "fp32_bytes": fp32_path.stat().st_size,
        "int8_bytes": int8_path.stat().st_size,
        "dataset_marker": "synthetic" if (args.data / "SYNTHETIC.txt").exists() else "collected",
    }
    (args.out / "train_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(args.data, args.out, names)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
