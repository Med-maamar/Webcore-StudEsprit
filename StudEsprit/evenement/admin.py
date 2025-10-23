from django.contrib import admin
from .models import Event, EventRegistration

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_datetime", "location", "organizer", "is_public")
    search_fields = ("title", "description", "location")
    list_filter = ("is_public", "start_datetime")

@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("event", "student", "full_name", "email", "is_approved", "submitted_at")
    search_fields = ("full_name", "email", "motivation", "additional_info")
    list_filter = ("is_approved", "event")
