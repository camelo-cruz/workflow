from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    # Home page
    path("", TemplateView.as_view(template_name="index.html"), name="index"),

    # Single SSE endpoint to start + stream your job
    path("stream/", views.stream, name="stream"),

    # OneDrive OAuth
    path("auth/start",    views.start_onedrive_auth,   name="start_onedrive_auth"),
    path("auth/redirect", views.onedrive_auth_redirect, name="onedrive_auth_redirect"),
    path("auth/token",    views.get_access_token,       name="get_access_token"),
]
