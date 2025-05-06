from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="index"),
    path("process/",              views.process, name="process"),
    path("stream/<str:job_id>/",  views.stream,  name="stream"),
    path("cancel/",               views.cancel,  name="cancel"),
    path("auth/start",            views.start_onedrive_auth,   name="start_onedrive_auth"),
    path("auth/redirect",         views.onedrive_auth_redirect, name="onedrive_auth_redirect"),
    path("auth/token",            views.get_access_token,       name="get_access_token"),
    path('download/<str:job_id>/', views.download_zip, name='download_zip'),
    path("terms/", views.terms_view, name="terms"),
    path("privacy/", views.privacy_view, name="privacy"),
]
