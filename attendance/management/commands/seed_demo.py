"""
Seed demo data for local testing: a few sections, each with 10 students.

Usage:
    python manage.py seed_demo

Face embeddings are NOT created here (there's no real face data to embed) -
enroll real faces via /enroll/<student_id>/ for anyone you want the
recognition/kiosk flow to actually match.
"""
from django.core.management.base import BaseCommand
from attendance.models import Section, Student

SECTIONS = ['BCSIT 4th Sem A', 'BCSIT 4th Sem B', 'BCA 6th Sem']

FIRST_NAMES = ['Aarav', 'Bibek', 'Chandra', 'Diya', 'Esha', 'Farhan', 'Gita', 'Hari', 'Isha', 'Jeevan']
LAST_NAMES = ['Shrestha', 'Gurung', 'Thapa', 'Rai', 'Karki', 'Poudel', 'Adhikari', 'Basnet', 'Magar', 'Tamang']


class Command(BaseCommand):
    help = 'Seed demo sections and 10 students per section for local testing.'

    def handle(self, *args, **options):
        for si, section_name in enumerate(SECTIONS, start=1):
            section, created = Section.objects.get_or_create(name=section_name)
            self.stdout.write(self.style.SUCCESS(f'Section: {section.name}' + (' (created)' if created else ' (exists)')))

            for i in range(1, 11):
                roll_number = f'2024-{si:02d}{i:02d}'
                full_name = f'{FIRST_NAMES[i - 1]} {LAST_NAMES[(i + si) % 10]}'
                student, created = Student.objects.get_or_create(
                    roll_number=roll_number,
                    defaults={
                        'full_name': full_name,
                        'section': section,
                        'consent_given': True,
                    },
                )
                status = 'created' if created else 'exists'
                self.stdout.write(f'  {roll_number}  {full_name}  ({status})')

        total_sections = Section.objects.count()
        total_students = Student.objects.count()
        self.stdout.write(self.style.SUCCESS(f'\nDone. {total_sections} sections, {total_students} students total.'))
