# This project uses MongoDB via PyMongo and custom services in `program.services`.
# Django's built-in admin works with Django ORM models and is not used here.
# If you later add Django models for Niveau you can register them below.

# from django.contrib import admin
# from .models import Niveau
# 
# @admin.register(Niveau)
# class NiveauAdmin(admin.ModelAdmin):
#     list_display = ("nom", "description")
#     search_fields = ("nom",)
