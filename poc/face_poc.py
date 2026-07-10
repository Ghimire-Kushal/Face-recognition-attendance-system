"""
Day 1-2 proof-of-concept: confirm InsightFace (buffalo_l, CPU) runs locally
and produces sensible cosine-similarity scores between two face photos.

Usage:
    python poc/face_poc.py photo1.jpg photo2.jpg

Put two test photos in poc/samples/ (e.g. two shots of yourself, and one of
a friend) and compare same-person vs different-person scores.
"""
import sys
import numpy as np
from insightface.app import FaceAnalysis


def load_embedding(app: FaceAnalysis, image_path: str) -> np.ndarray:
    import cv2

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    faces = app.get(img)
    if len(faces) == 0:
        raise ValueError(f"No face detected in {image_path}")
    if len(faces) > 1:
        print(f"Warning: {len(faces)} faces found in {image_path}, using the largest")
        faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)

    return faces[0].normed_embedding  # already L2-normalized, 512-dim


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # both vectors are already unit-normalized


def main():
    if len(sys.argv) != 3:
        print("Usage: python poc/face_poc.py <image1> <image2>")
        sys.exit(1)

    print("Loading buffalo_l model (first run downloads ~300MB, be patient)...")
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    print("Model loaded.\n")

    path1, path2 = sys.argv[1], sys.argv[2]

    emb1 = load_embedding(app, path1)
    emb2 = load_embedding(app, path2)

    score = cosine_similarity(emb1, emb2)

    print(f"Embedding dim: {emb1.shape[0]}")
    print(f"Cosine similarity: {score:.4f}")

    if score > 0.5:
        print("-> Likely the SAME person")
    elif score > 0.35:
        print("-> Borderline / uncertain (threshold tuning needed)")
    else:
        print("-> Likely DIFFERENT people")


if __name__ == "__main__":
    main()
