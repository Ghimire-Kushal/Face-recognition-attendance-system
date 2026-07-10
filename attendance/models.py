from django.db import models


class Section(models.Model):
    name = models.CharField(max_length=100, unique=True)  # e.g. "BCSIT 4th Sem A"

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Student(models.Model):
    full_name = models.CharField(max_length=150)
    roll_number = models.CharField(max_length=30, unique=True)
    email = models.EmailField(blank=True)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='students')
    enrolled_photo = models.ImageField(upload_to='enrolled_photos/', blank=True, null=True)
    consent_given = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['roll_number']

    def __str__(self):
        return f"{self.roll_number} - {self.full_name}"

    @property
    def is_enrolled(self):
        return self.embeddings.exists()


class FaceEmbedding(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='embeddings')
    vector = models.JSONField()  # list of 512 floats, L2-normalized
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Embedding for {self.student.roll_number} ({self.created_at:%Y-%m-%d %H:%M})"


class AttendanceSession(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='sessions')
    date = models.DateField(auto_now_add=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.section.name} - {self.date}"


class AttendanceRecord(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    marked_at = models.DateTimeField(auto_now_add=True)
    confidence = models.FloatField()

    class Meta:
        unique_together = ('session', 'student')
        ordering = ['-marked_at']

    def __str__(self):
        return f"{self.student.roll_number} @ {self.session}"
