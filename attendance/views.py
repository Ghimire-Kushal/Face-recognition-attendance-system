import base64
import csv
import datetime
import json

import cv2
import numpy as np
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from . import face_engine, matcher
from .models import AttendanceRecord, AttendanceSession, FaceEmbedding, Section, Student


# ---------- helpers ----------

def _decode_base64_image(data_url: str) -> np.ndarray:
    """'data:image/jpeg;base64,....' -> BGR numpy array."""
    if ',' in data_url:
        data_url = data_url.split(',', 1)[1]
    raw = base64.b64decode(data_url)
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError('bad_image')
    return img


ENROLL_ANGLES = ['straight', 'left', 'right', 'up', 'down']


# ---------- dashboard ----------

@login_required
def dashboard(request):
    section_id = request.GET.get('section')
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')

    sessions = AttendanceSession.objects.select_related('section').all()
    if section_id:
        sessions = sessions.filter(section_id=section_id)
    if date_from:
        sessions = sessions.filter(date__gte=date_from)
    if date_to:
        sessions = sessions.filter(date__lte=date_to)

    today_sessions = sessions.filter(date=timezone.localdate()).annotate(
        present_count=Count('records', distinct=True)
    )

    section_stats = []
    for section in Section.objects.all():
        total_students = section.students.count()
        today_session = AttendanceSession.objects.filter(
            section=section, date=timezone.localdate()
        ).order_by('-start_time').first()
        present = today_session.records.count() if today_session else 0
        section_stats.append({
            'section': section,
            'total_students': total_students,
            'present': present,
            'absent': max(total_students - present, 0),
            'session': today_session,
        })

    return render(request, 'attendance/dashboard.html', {
        'today_sessions': today_sessions,
        'section_stats': section_stats,
        'sections': Section.objects.all(),
        'selected_section': int(section_id) if section_id else None,
        'date_from': date_from or '',
        'date_to': date_to or '',
    })


# ---------- students ----------

@login_required
def student_list(request):
    students = Student.objects.select_related('section').all()
    return render(request, 'attendance/student_list.html', {'students': students, 'sections': Section.objects.all()})


@login_required
@require_POST
def student_add(request):
    full_name = request.POST.get('full_name', '').strip()
    roll_number = request.POST.get('roll_number', '').strip()
    section_id = request.POST.get('section')
    consent_given = request.POST.get('consent_given') == 'on'

    if full_name and roll_number and section_id and consent_given:
        Student.objects.create(
            full_name=full_name,
            roll_number=roll_number,
            section_id=section_id,
            consent_given=consent_given,
        )
    return redirect('student_list')


@login_required
def student_detail(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    since = timezone.localdate() - datetime.timedelta(days=30)
    records = (AttendanceRecord.objects
               .filter(student=student, session__date__gte=since)
               .select_related('session')
               .order_by('session__date'))

    total_sessions = AttendanceSession.objects.filter(
        section=student.section, date__gte=since
    ).count()
    present_count = records.count()
    attendance_pct = round((present_count / total_sessions) * 100, 1) if total_sessions else 0

    chart_labels = [r.session.date.isoformat() for r in records]
    chart_data = [1] * len(records)

    return render(request, 'attendance/student_detail.html', {
        'student': student,
        'records': records,
        'attendance_pct': attendance_pct,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'embeddings': student.embeddings.order_by('created_at'),
    })


@login_required
@require_POST
def student_delete_data(request, student_id):
    """Privacy: wipe a student's biometric data (embeddings + enrolled photo) on request."""
    student = get_object_or_404(Student, pk=student_id)
    student.embeddings.all().delete()
    if student.enrolled_photo:
        student.enrolled_photo.delete(save=False)
        student.enrolled_photo = None
    student.consent_given = False
    student.save()
    matcher.refresh()
    return redirect('student_detail', student_id=student.id)


@login_required
@require_POST
def embedding_delete(request, embedding_id):
    """Delete a single bad enrollment angle without wiping the whole enrollment."""
    embedding = get_object_or_404(FaceEmbedding, pk=embedding_id)
    student_id = embedding.student_id
    embedding.delete()
    matcher.refresh()
    return redirect('student_detail', student_id=student_id)


# ---------- enrollment ----------

@login_required
@ensure_csrf_cookie
def enroll_page(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    return render(request, 'attendance/enroll.html', {
        'student': student,
        'angles': ENROLL_ANGLES,
    })


@login_required
@require_POST
def api_enroll(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    try:
        payload = json.loads(request.body)
        image = _decode_base64_image(payload['image'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'invalid_payload'}, status=400)

    faces = face_engine.detect_faces(image)
    if len(faces) == 0:
        return JsonResponse({'ok': False, 'error': 'no_face', 'message': 'No face detected. Move closer / check lighting.'}, status=422)
    if len(faces) > 1:
        return JsonResponse({'ok': False, 'error': 'multiple_faces', 'message': 'Multiple faces detected. Make sure only you are in frame.'}, status=422)

    embedding = faces[0].normed_embedding
    FaceEmbedding.objects.create(student=student, vector=embedding.tolist())
    matcher.refresh()

    count = student.embeddings.count()
    return JsonResponse({'ok': True, 'total_captured': count})


# ---------- sessions ----------

@login_required
def session_list(request):
    if request.method == 'POST':
        section_id = request.POST.get('section')
        if section_id and not AttendanceSession.objects.filter(section_id=section_id, is_active=True).exists():
            AttendanceSession.objects.create(section_id=section_id)
        return redirect('session_list')

    sessions = AttendanceSession.objects.select_related('section').annotate(present_count=Count('records'))
    return render(request, 'attendance/session_list.html', {
        'sessions': sessions,
        'sections': Section.objects.all(),
    })


@login_required
@require_POST
def session_end(request, session_id):
    session = get_object_or_404(AttendanceSession, pk=session_id)
    session.is_active = False
    session.end_time = timezone.now()
    session.save()
    return redirect('session_list')


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(AttendanceSession.objects.select_related('section'), pk=session_id)
    records = session.records.select_related('student').order_by('-marked_at')
    return render(request, 'attendance/session_detail.html', {
        'session': session,
        'records': records,
        'present_count': records.count(),
        'total_students': session.section.students.count(),
    })


@login_required
def session_report(request, session_id):
    session = get_object_or_404(AttendanceSession.objects.select_related('section'), pk=session_id)
    present_records = session.records.select_related('student').order_by('student__roll_number')
    present_ids = present_records.values_list('student_id', flat=True)
    absent_students = session.section.students.exclude(id__in=present_ids).order_by('roll_number')

    return render(request, 'attendance/session_report.html', {
        'session': session,
        'present_records': present_records,
        'absent_students': absent_students,
        'absent_with_email': absent_students.exclude(email='').count(),
    })


@login_required
@require_POST
def session_notify_absentees(request, session_id):
    """Email every absent student with an address on file. Uses the
    console backend in dev (prints to the runserver terminal) and real SMTP
    in prod - see config/settings/dev.py and prod.py."""
    session = get_object_or_404(AttendanceSession.objects.select_related('section'), pk=session_id)
    present_ids = session.records.values_list('student_id', flat=True)
    absentees = session.section.students.exclude(id__in=present_ids).exclude(email='')

    sent = 0
    for student in absentees:
        send_mail(
            subject=f'Absence recorded — {session.section.name}, {session.date}',
            message=(
                f'Hi {student.full_name},\n\n'
                f'You were marked absent for {session.section.name} on {session.date}. '
                f'If this is a mistake, contact your instructor.\n\n'
                f'- FaceRoll Attendance'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.email],
            fail_silently=True,
        )
        sent += 1

    messages.success(request, f'Sent {sent} absence notification email(s).')
    return redirect('session_report', session_id=session.id)


@login_required
def session_export_csv(request, session_id):
    session = get_object_or_404(AttendanceSession.objects.select_related('section'), pk=session_id)
    present_records = session.records.select_related('student').order_by('student__roll_number')
    all_students = session.section.students.order_by('roll_number')

    filename = f"attendance_{session.section.name.replace(' ', '')}_{session.date}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Roll Number', 'Name', 'Status', 'Time Marked', 'Confidence'])

    records_by_student = {r.student_id: r for r in present_records}
    for student in all_students:
        record = records_by_student.get(student.id)
        if record:
            writer.writerow([student.roll_number, student.full_name, 'Present',
                              timezone.localtime(record.marked_at).strftime('%H:%M:%S'),
                              f'{record.confidence:.3f}'])
        else:
            writer.writerow([student.roll_number, student.full_name, 'Absent', '', ''])

    return response


@login_required
def section_export_range_csv(request, section_id):
    section = get_object_or_404(Section, pk=section_id)
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')

    sessions = AttendanceSession.objects.filter(section=section)
    if date_from:
        sessions = sessions.filter(date__gte=date_from)
    if date_to:
        sessions = sessions.filter(date__lte=date_to)
    sessions = sessions.order_by('date')
    dates = list(dict.fromkeys(s.date for s in sessions))  # unique, ordered

    students = section.students.order_by('roll_number')
    records = AttendanceRecord.objects.filter(session__in=sessions).select_related('session')
    present_lookup = {(r.student_id, r.session.date) for r in records}

    filename = f"attendance_{section.name.replace(' ', '')}_range.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Roll Number', 'Name'] + [d.isoformat() for d in dates] + ['Attendance %'])

    for student in students:
        row = [student.roll_number, student.full_name]
        present_count = 0
        for d in dates:
            present = (student.id, d) in present_lookup
            present_count += int(present)
            row.append('P' if present else 'A')
        pct = round((present_count / len(dates)) * 100, 1) if dates else 0
        row.append(pct)
        writer.writerow(row)

    return response


# ---------- kiosk ----------

@login_required
@ensure_csrf_cookie
def kiosk_page(request, session_id):
    session = get_object_or_404(AttendanceSession.objects.select_related('section'), pk=session_id)
    enrolled_count = Student.objects.filter(section=session.section, embeddings__isnull=False).distinct().count()
    return render(request, 'attendance/kiosk.html', {
        'session': session,
        'liveness_required': settings.LIVENESS_REQUIRED,
        'enrolled_count': enrolled_count,
    })


# ---------- recognition API ----------

@login_required
@require_POST
def api_recognize(request):
    try:
        payload = json.loads(request.body)
        image = _decode_base64_image(payload['image'])
        session_id = payload.get('session_id')
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'invalid_payload'}, status=400)

    session = None
    if session_id:
        session = AttendanceSession.objects.filter(pk=session_id, is_active=True).first()

    faces = face_engine.detect_faces(image)
    threshold = settings.FACE_MATCH_THRESHOLD
    low_floor = settings.FACE_LOW_CONFIDENCE_FLOOR

    results = []
    for face in faces:
        student, score = matcher.match(face.normed_embedding)
        x1, y1, x2, y2 = [float(v) for v in face.bbox]
        entry = {
            'bbox': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2},
            'confidence': round(score, 4),
        }

        if student is None or score < low_floor:
            entry.update({'status': 'unknown', 'name': None, 'roll_number': None})
        elif score < threshold:
            entry.update({
                'status': 'low_confidence',
                'name': student.full_name,
                'roll_number': student.roll_number,
            })
        else:
            entry.update({
                'status': 'matched',
                'name': student.full_name,
                'roll_number': student.roll_number,
                'student_id': student.id,
            })
            if session:
                record, created = AttendanceRecord.objects.get_or_create(
                    session=session, student=student,
                    defaults={'confidence': score},
                )
                entry['marked'] = created
                entry['already_marked'] = not created
                entry['marked_at'] = timezone.localtime(record.marked_at).strftime('%I:%M %p')
            else:
                entry['marked'] = False
                entry['already_marked'] = False

        results.append(entry)

    return JsonResponse({'ok': True, 'faces': results})
