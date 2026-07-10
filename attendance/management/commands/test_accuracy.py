"""
Field-testing tool for Day 18-19: measure recognition accuracy at several
candidate thresholds so you can pick the best FACE_MATCH_THRESHOLD.

Usage:
    python manage.py test_accuracy /path/to/test_photos/

Expected folder layout - one subfolder per roll number, containing photos
of that student taken under real conditions (classroom lighting, glasses
on/off, different distances):

    test_photos/
        2024-001/
            photo1.jpg
            photo2.jpg
        2024-002/
            photo1.jpg
        ...

Each photo is embedded and matched against the full enrolled population
(from the DB) using the SAME matcher used in production. We report, for
each threshold: correct matches, misses (should have matched but score
fell under threshold), and false matches (matched the wrong student).
"""
import os

import cv2
from django.core.management.base import BaseCommand, CommandError

from attendance import face_engine, matcher
from attendance.models import Student

THRESHOLDS_TO_TEST = [0.30, 0.35, 0.40, 0.45, 0.50]


class Command(BaseCommand):
    help = 'Measure recognition accuracy across candidate thresholds using a folder of labeled test photos.'

    def add_arguments(self, parser):
        parser.add_argument('folder', type=str, help='Path to folder of subfolders named by roll_number')

    def handle(self, *args, **options):
        folder = options['folder']
        if not os.path.isdir(folder):
            raise CommandError(f'Not a directory: {folder}')

        matcher.refresh()

        # score, true_roll, matched_roll (best match regardless of threshold)
        results = []

        for roll_number in sorted(os.listdir(folder)):
            student_dir = os.path.join(folder, roll_number)
            if not os.path.isdir(student_dir):
                continue

            true_student = Student.objects.filter(roll_number=roll_number).first()
            if true_student is None:
                self.stdout.write(self.style.WARNING(f'No enrolled student with roll_number={roll_number}, skipping'))
                continue

            for fname in sorted(os.listdir(student_dir)):
                path = os.path.join(student_dir, fname)
                img = cv2.imread(path)
                if img is None:
                    continue

                faces = face_engine.detect_faces(img)
                if len(faces) != 1:
                    self.stdout.write(self.style.WARNING(f'{path}: expected 1 face, found {len(faces)}, skipping'))
                    continue

                matched_student, score = matcher.match(faces[0].normed_embedding)
                results.append({
                    'path': path,
                    'true_roll': roll_number,
                    'matched_roll': matched_student.roll_number if matched_student else None,
                    'score': score,
                })

        if not results:
            self.stdout.write(self.style.ERROR('No usable test photos found.'))
            return

        self.stdout.write(f'\nEvaluated {len(results)} photos across {len(set(r["true_roll"] for r in results))} students.\n')
        self.stdout.write(f"{'Threshold':<10}{'Correct':<10}{'Misses':<10}{'False matches':<16}")

        for threshold in THRESHOLDS_TO_TEST:
            correct = misses = false_matches = 0
            for r in results:
                if r['score'] >= threshold:
                    if r['matched_roll'] == r['true_roll']:
                        correct += 1
                    else:
                        false_matches += 1
                else:
                    misses += 1
            marker = '  <-- current setting' if abs(threshold - self._current_threshold()) < 1e-6 else ''
            self.stdout.write(f'{threshold:<10}{correct:<10}{misses:<10}{false_matches:<16}{marker}')

        self.stdout.write('\nGuidance: pick the threshold with the fewest false matches while keeping misses low.')
        self.stdout.write('False matches are worse than misses for attendance (marks the wrong student present).')

    @staticmethod
    def _current_threshold():
        from django.conf import settings
        return settings.FACE_MATCH_THRESHOLD
