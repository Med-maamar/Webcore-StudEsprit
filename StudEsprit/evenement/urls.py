from django.urls import path
from . import views

app_name = 'evenement'

urlpatterns = [
    path('', views.event_list, name='event_list'),
    path('event/<int:event_id>/', views.event_detail, name='event_detail'),
    path('event/<int:event_id>/register/', views.event_register, name='event_register'),
    path('event/<int:event_id>/admin/registrations/', views.registrations_admin, name='registrations_admin'),
    path('event/<int:event_id>/edit/', views.event_edit, name='event_edit'),
    path('create/', views.event_create, name='event_create'),
    path('event/<int:event_id>/delete/', views.event_delete, name='event_delete'),
]
