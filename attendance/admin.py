from django.contrib import admin
from .models import Section, Student, FaceEmbedding, AttendanceSession, AttendanceRecord


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('roll_number', 'full_name', 'section', 'consent_given', 'is_enrolled', 'created_at')
    list_filter = ('section', 'consent_given')
    search_fields = ('roll_number', 'full_name')

    @admin.display(boolean=True)
    def is_enrolled(self, obj):
        return obj.is_enrolled


@admin.register(FaceEmbedding)
class FaceEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('student', 'created_at')
    search_fields = ('student__roll_number', 'student__full_name')
    list_filter = ('created_at',)


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('section', 'date', 'start_time', 'end_time', 'is_active')
    list_filter = ('section', 'is_active', 'date')


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'marked_at', 'confidence')
    list_filter = ('session__section', 'session')
    search_fields = ('student__roll_number', 'student__full_name')
