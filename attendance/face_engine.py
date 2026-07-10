"""
Lazily-loaded, process-wide singleton InsightFace app.

InsightFace model loading takes a couple of seconds and holds onnxruntime
sessions in memory - we load it exactly once per process, not per-request.
"""
import threading
import numpy as np
from django.conf import settings

_app = None
_lock = threading.Lock()


def get_app():
    global _app
    if _app is None:
        with _lock:
            if _app is None:  # re-check inside the lock (double-checked locking)
                from insightface.app import FaceAnalysis
                app = FaceAnalysis(
                    name=settings.INSIGHTFACE_MODEL_NAME,
                    providers=['CPUExecutionProvider'],
                )
                app.prepare(ctx_id=0, det_size=(640, 640))
                _app = app
    return _app


def detect_faces(image_bgr: np.ndarray):
    """Returns the list of insightface Face objects found in a BGR image."""
    app = get_app()
    return app.get(image_bgr)


def get_embedding(image_bgr: np.ndarray) -> np.ndarray:
    """
    Convenience helper for the enrollment flow: expects exactly one face.
    Raises ValueError if zero or multiple faces are found.
    """
    faces = detect_faces(image_bgr)
    if len(faces) == 0:
        raise ValueError('no_face')
    if len(faces) > 1:
        raise ValueError('multiple_faces')
    return faces[0].normed_embedding
