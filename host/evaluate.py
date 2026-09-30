"""Compare FP32 and INT8 models, plus rejection and the vote state machine."""

import json
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image

from gesture_vote import GestureControl

INPUT = 128
CONFIDENCE_MIN = 0.70


def load_images(folder, size):
    paths = sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.png"))
    images = []
    for path in paths:
        image = Image.open(path).convert("RGB").resize((size, size))
        images.append(np.asarray(image, dtype=np.float32))
    if not images:
        raise SystemExit(f"no images in {folder}")
    return np.stack(images)


def load_labeled(root, names):
    images = []
    labels = []
    for index, name in enumerate(names):
        batch = load_images(root / name, INPUT)
        images.append(batch)
        labels.append(np.full(len(batch), index, dtype=np.int32))
    return np.concatenate(images), np.concatenate(labels)


def quantize_input(images, detail):
    scale, zero = detail["quantization"]
    if not scale:
        return images.astype(np.float32)
    quantized = np.round(images / scale + zero)
    return np.clip(quantized, -128, 127).astype(np.int8)


def predict(path, images):
    interpreter = tf.lite.Interpreter(model_path=str(path))
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    batch = quantize_input(images, input_detail) if input_detail["dtype"] == np.int8 else images
    started = time.perf_counter()
    outputs = []
    for row in batch:
        interpreter.set_tensor(input_detail["index"], row[None, ...])
        interpreter.invoke()
        outputs.append(interpreter.get_tensor(output_detail["index"])[0])
    elapsed_ms = (time.perf_counter() - started) * 1000.0 / len(batch)
    probs = np.stack(outputs).astype(np.float32)
    if probs.ndim != 2:
        raise SystemExit(f"unexpected output shape {probs.shape} from {path}")
    return probs, elapsed_ms, path.stat().st_size


def scores(probs, labels, names):
    pred = np.argmax(probs, axis=1)
    confidence = probs.max(axis=1)
    accepted = confidence >= CONFIDENCE_MIN
    matrix = np.zeros((len(names), len(names)), dtype=np.int32)
    for truth, guess in zip(labels, pred):
        matrix[int(truth), int(guess)] += 1
    accuracy = float(np.mean(pred == labels))
    accepted_accuracy = float(np.mean(pred[accepted] == labels[accepted])) if np.any(accepted) else 0.0
    return {
        "accuracy": accuracy,
        "accepted_fraction": float(np.mean(accepted)),
        "accepted_accuracy": accepted_accuracy,
        "confusion": matrix.tolist(),
        "mean_confidence": float(np.mean(confidence)),
    }


def rejection_rate(probs):
    return float(np.mean(probs.max(axis=1) < CONFIDENCE_MIN))


def vote_on_predictions(pred, confidence):
    voted = GestureControl()
    direct_hold = None
    vote_moves = 0
    direct_moves = 0
    for class_id, conf in zip(pred, confidence):
        if voted.update(int(class_id), float(conf))[0]:
            vote_moves += 1
        if conf >= CONFIDENCE_MIN and class_id != direct_hold:
            direct_hold = int(class_id)
            direct_moves += 1
    return {"vote_moves": vote_moves, "direct_moves": direct_moves, "frames": int(len(pred))}


def write_report(data_root, artifact_dir, names):
    test_x, test_y = load_labeled(data_root / "test", names)
    unknown = load_images(data_root / "unknown", INPUT)
    fp32, fp32_ms, fp32_bytes = predict(artifact_dir / "gesture_fp32.tflite", test_x)
    int8, int8_ms, int8_bytes = predict(artifact_dir / "gesture_int8.tflite", test_x)
    unknown_int8, _, _ = predict(artifact_dir / "gesture_int8.tflite", unknown)
    int8_pred = np.argmax(int8, axis=1)
    scripted = []
    for class_id in range(len(names)):
        scripted.extend([class_id, class_id, class_id, (class_id + 1) % len(names), class_id, class_id, class_id])
    scripted = np.asarray(scripted, dtype=np.int32)
    report = {
        "dataset_marker": "synthetic" if (data_root / "SYNTHETIC.txt").exists() else "collected",
        "labels": list(names),
        "confidence_min": CONFIDENCE_MIN,
        "fp32": {
            **scores(fp32, test_y, names),
            "mean_invoke_ms": fp32_ms,
            "tflite_bytes": fp32_bytes,
        },
        "int8": {
            **scores(int8, test_y, names),
            "mean_invoke_ms": int8_ms,
            "tflite_bytes": int8_bytes,
            "unknown_rejection_rate": rejection_rate(unknown_int8),
            "control_on_test": vote_on_predictions(int8_pred, int8.max(axis=1)),
            "control_with_glitches": vote_on_predictions(scripted, np.full(len(scripted), 0.95)),
        },
        "board": {
            "infer_ms": None,
            "capture_ms": None,
            "servo_motion_ms": None,
            "note": "Fill from USART after flashing. End-to-end ms is (vote_frames-1)*frame_period + infer_ms + servo_motion_ms.",
        },
    }
    destination = artifact_dir / "eval_report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {destination}")
    return report
