from django.urls import path
from . import views

urlpatterns = [
    path('', views.notification_list, name='notifications'),
    path('mark-as-read/<int:notification_id>/', views.mark_as_read, name='mark_as_read'),
]
