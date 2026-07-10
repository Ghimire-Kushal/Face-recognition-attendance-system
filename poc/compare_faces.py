"""
Compare two face photos using InsightFace (buffalo_l, CPU) and cosine similarity.

Usage:
    python poc/compare_faces.py image1.jpg image2.jpg

Threshold: 0.40 (tune later in Day 18-19 with test_accuracy command)
"""
import sys
import cv2
import numpy as np
from insightface.app import FaceAnalysis

THRESHOLD = 0.40


def get_embedding(app: FaceAnalysis, image_path: str) -> np.ndarray:
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    faces = app.get(img)
    if len(faces) == 0:
        raise ValueError(f"No face detected in {image_path}")
    if len(faces) > 1:
        print(f"Warning: {len(faces)} faces found in {image_path}, using the largest")
        faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)

    return faces[0].normed_embedding  # unit-normalized, 512-dim


def main():
    if len(sys.argv) != 3:
        print("Usage: python poc/compare_faces.py <image1> <image2>")
        sys.exit(1)

    print("Loading buffalo_l (first run downloads ~300MB to ~/.insightface)...")
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    print("Model ready.\n")

    emb1 = get_embedding(app, sys.argv[1])
    emb2 = get_embedding(app, sys.argv[2])

    # Both vectors are already L2-normalized, so dot product == cosine similarity
    score = float(np.dot(emb1, emb2))

    print(f"Cosine similarity: {score:.4f}  (threshold: {THRESHOLD})")
    print("Verdict: SAME PERSON" if score >= THRESHOLD else "Verdict: DIFFERENT PERSON")


if __name__ == "__main__":
    main()
