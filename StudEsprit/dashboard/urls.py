from django.urls import path
from dashboard import views


urlpatterns = [
    path("", views.index, name="dashboard_index"),
    path("users", views.users_page, name="dashboard_users"),
    path("users/partial", views.users_partial, name="dashboard_users_partial"),
    path("users/update-role", views.users_update_role, name="dashboard_users_update_role"),
]

