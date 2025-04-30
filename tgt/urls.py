from django.urls import path
from django.views.generic import TemplateView
from django.http import HttpResponse

from . import views

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    path('process/', views.process, name='process'),
    path('logs/<str:job_id>', views.logs, name='logs'),
    path('cancel/<str:job_id>', views.cancel, name='cancel'),
]