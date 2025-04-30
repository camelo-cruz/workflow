from django.urls import path
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from . import views

urlpatterns = [
    path('', ensure_csrf_cookie(TemplateView.as_view(template_name='index.html')), name='index'),
    path('process/', views.process, name='process'),
    path('logs/<str:job_id>', views.logs, name='logs'),
    path('cancel/<str:job_id>', views.cancel, name='cancel'),
]