import base64
import json
from unittest.mock import MagicMock, patch

import numpy as np
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from . import matcher
from .models import AttendanceSession, FaceEmbedding, Section, Student


def _unit_vector(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.normal(size=512).astype(np.float32)
    return v / np.linalg.norm(v)


class MatcherTests(TestCase):
    def setUp(self):
        self.section = Section.objects.create(name='Section A')
        self.alice = Student.objects.create(full_name='Alice', roll_number='A1', section=self.section)
        self.bob = Student.objects.create(full_name='Bob', roll_number='B1', section=self.section)

        self.alice_vec = _unit_vector(1)
        self.bob_vec = _unit_vector(2)
        FaceEmbedding.objects.create(student=self.alice, vector=self.alice_vec.tolist())
        # a second angle for alice - matcher should take the MAX across a student's rows
        FaceEmbedding.objects.create(student=self.alice, vector=_unit_vector(3).tolist())
        FaceEmbedding.objects.create(student=self.bob, vector=self.bob_vec.tolist())
        matcher.refresh()

    def test_no_enrolled_students_returns_none(self):
        FaceEmbedding.objects.all().delete()
        matcher.refresh()
        student, score = matcher.match(_unit_vector(99))
        self.assertIsNone(student)
        self.assertEqual(score, 0.0)

    def test_exact_embedding_matches_correct_student(self):
        student, score = matcher.match(self.alice_vec)
        self.assertEqual(student.id, self.alice.id)
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_distinguishes_between_students(self):
        student, score = matcher.match(self.bob_vec)
        self.assertEqual(student.id, self.bob.id)
        self.assertNotEqual(student.id, self.alice.id)

    def test_refresh_reflects_deleted_embeddings(self):
        self.bob.embeddings.all().delete()
        matcher.refresh()
        student, score = matcher.match(self.bob_vec)
        # only Alice left enrolled - the closest match now must be Alice, not Bob
        self.assertEqual(student.id, self.alice.id)


@override_settings(FACE_MATCH_THRESHOLD=0.40, FACE_LOW_CONFIDENCE_FLOOR=0.30)
class RecognizeThresholdTests(TestCase):
    """api_recognize's status classification against FACE_MATCH_THRESHOLD / FACE_LOW_CONFIDENCE_FLOOR."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pw12345')
        self.client.force_login(self.user)
        self.section = Section.objects.create(name='Section A')
        self.student = Student.objects.create(full_name='Alice', roll_number='A1', section=self.section)
        self.session = AttendanceSession.objects.create(section=self.section)

    def _post_recognize(self, score, session_id=None):
        fake_face = MagicMock()
        fake_face.bbox = [0, 0, 10, 10]
        fake_face.normed_embedding = _unit_vector(1)

        payload = {
            'image': 'data:image/jpeg;base64,' + base64.b64encode(b'fake').decode(),
        }
        if session_id is not None:
            payload['session_id'] = session_id

        with patch('attendance.views.face_engine.detect_faces', return_value=[fake_face]), \
             patch('attendance.views.cv2.imdecode', return_value=np.zeros((10, 10, 3), dtype=np.uint8)), \
             patch('attendance.views.matcher.match', return_value=(self.student, score)):
            return self.client.post(
                '/api/recognize/', data=json.dumps(payload), content_type='application/json',
            )

    def test_score_above_threshold_is_matched(self):
        response = self._post_recognize(score=0.50, session_id=self.session.id)
        entry = response.json()['faces'][0]
        self.assertEqual(entry['status'], 'matched')
        self.assertTrue(entry['marked'])

    def test_score_between_floor_and_threshold_is_low_confidence(self):
        response = self._post_recognize(score=0.35, session_id=self.session.id)
        entry = response.json()['faces'][0]
        self.assertEqual(entry['status'], 'low_confidence')
        self.assertNotIn('marked', entry)

    def test_score_below_floor_is_unknown(self):
        response = self._post_recognize(score=0.10, session_id=self.session.id)
        entry = response.json()['faces'][0]
        self.assertEqual(entry['status'], 'unknown')
        self.assertIsNone(entry['name'])

    def test_duplicate_recognition_does_not_double_mark(self):
        """Two matches of the same student in one session must only create one AttendanceRecord."""
        self._post_recognize(score=0.90, session_id=self.session.id)
        response = self._post_recognize(score=0.90, session_id=self.session.id)
        entry = response.json()['faces'][0]

        self.assertFalse(entry['marked'])
        self.assertTrue(entry['already_marked'])
        self.assertEqual(self.session.records.filter(student=self.student).count(), 1)

    def test_no_active_session_does_not_mark_attendance(self):
        response = self._post_recognize(score=0.90, session_id=None)
        entry = response.json()['faces'][0]
        self.assertEqual(entry['status'], 'matched')
        self.assertFalse(entry['marked'])
        self.assertEqual(self.session.records.count(), 0)


@override_settings(AXES_FAILURE_LIMIT=5, AXES_COOLOFF_TIME=1)
class LoginLockoutTests(TestCase):
    """django-axes should lock out repeated failed logins against the teacher login."""

    def setUp(self):
        User.objects.create_user(username='teacher', password='correct-password')

    def _attempt(self, password):
        return self.client.post(reverse('login'), {'username': 'teacher', 'password': password})

    def test_correct_password_logs_in(self):
        response = self._attempt('correct-password')
        self.assertRedirects(response, '/dashboard/')

    def test_locked_out_after_repeated_failures(self):
        for _ in range(5):
            self._attempt('wrong-password')

        # even the correct password is now rejected until the cooloff period passes
        response = self._attempt('correct-password')
        self.assertEqual(response.status_code, 429)
