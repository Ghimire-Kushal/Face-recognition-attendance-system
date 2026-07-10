"""
In-memory matcher: holds every student's face embeddings as one (N x 512)
normalized numpy matrix, so matching a live face against the whole enrolled
population is a single matrix multiply instead of N separate DB round trips.

Because a student can have several embeddings (different angles/lighting),
we keep a parallel `student_ids` array the same length as the matrix rows,
and when scoring we take the MAX similarity across all rows belonging to the
same student ("does this face match ANY of this student's enrolled looks").
"""
import threading
import numpy as np
from .models import FaceEmbedding, Student

_lock = threading.Lock()
_matrix: np.ndarray | None = None      # shape (N, 512)
_student_ids: np.ndarray | None = None  # shape (N,), parallel to _matrix rows
_student_cache: dict[int, Student] = {}


def refresh():
    """Rebuild the in-memory matrix from the database. Call after enrollment."""
    global _matrix, _student_ids, _student_cache
    with _lock:
        rows = list(FaceEmbedding.objects.select_related('student').all())
        if not rows:
            _matrix = np.zeros((0, 512), dtype=np.float32)
            _student_ids = np.array([], dtype=np.int64)
            _student_cache = {}
            return

        _matrix = np.array([r.vector for r in rows], dtype=np.float32)
        _student_ids = np.array([r.student_id for r in rows], dtype=np.int64)
        _student_cache = {r.student_id: r.student for r in rows}


def _ensure_loaded():
    if _matrix is None:
        refresh()


def match(embedding: np.ndarray):
    """
    Compare one face embedding against every enrolled student.

    Returns (student_or_None, best_score). student is None when there are
    no enrolled students at all.
    """
    _ensure_loaded()
    if _matrix.shape[0] == 0:
        return None, 0.0

    # matrix rows and query embedding are both L2-normalized (InsightFace's
    # normed_embedding), so a plain dot product IS cosine similarity.
    sims = _matrix @ embedding  # shape (N,)

    best_per_student: dict[int, float] = {}
    for sid, score in zip(_student_ids, sims):
        sid = int(sid)
        if sid not in best_per_student or score > best_per_student[sid]:
            best_per_student[sid] = float(score)

    best_student_id = max(best_per_student, key=best_per_student.get)
    best_score = best_per_student[best_student_id]
    return _student_cache[best_student_id], best_score
