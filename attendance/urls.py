from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path('students/', views.student_list, name='student_list'),
    path('students/add/', views.student_add, name='student_add'),
    path('students/<int:student_id>/', views.student_detail, name='student_detail'),
    path('students/<int:student_id>/delete-data/', views.student_delete_data, name='student_delete_data'),
    path('embeddings/<int:embedding_id>/delete/', views.embedding_delete, name='embedding_delete'),

    path('enroll/<int:student_id>/', views.enroll_page, name='enroll_page'),

    path('sessions/', views.session_list, name='session_list'),
    path('sessions/<int:session_id>/', views.session_detail, name='session_detail'),
    path('sessions/<int:session_id>/report/', views.session_report, name='session_report'),
    path('sessions/<int:session_id>/export/', views.session_export_csv, name='session_export_csv'),
    path('sessions/<int:session_id>/end/', views.session_end, name='session_end'),

    path('sections/<int:section_id>/export-range/', views.section_export_range_csv, name='section_export_range_csv'),

    path('kiosk/<int:session_id>/', views.kiosk_page, name='kiosk_page'),

    # API
    path('api/enroll/<int:student_id>/', views.api_enroll, name='api_enroll'),
    path('api/recognize/', views.api_recognize, name='api_recognize'),
]
