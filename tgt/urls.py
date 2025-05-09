from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path("", views.index, name="index"),

    # Path to the main page and authentication
    path("auth/start", views.start_onedrive_auth, name="start_onedrive_auth"),
    path("auth/redirect", views.onedrive_auth_redirect, name="onedrive_auth_redirect"),
    path("auth/token", views.get_access_token, name="get_access_token"),

    # Path to the process logics
    path("process/", views.process, name="process"),
    path("cancel/", views.cancel,  name="cancel"),
    path("stream/<str:job_id>/", views.stream,  name="stream"),
    path('download/<str:job_id>/', views.download_zip, name='download_zip'),

    # Path to the terms and privacy policy
    path("terms/", views.terms_view, name="terms"),
    path("privacy/", views.privacy_view, name="privacy"),
]
