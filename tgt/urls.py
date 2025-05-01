from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    path('process/', views.process, name='process'),
    path('logs/<str:job_id>', views.logs, name='logs'),
    path('cancel/<str:job_id>', views.cancel, name='cancel'),
    path("auth/start", views.start_onedrive_auth, name="start_onedrive_auth"),
    path("auth/redirect", views.onedrive_auth_redirect, name="onedrive_auth_redirect"),
    path("auth/token", views.get_access_token, name="get_access_token"),
]