from django.urls import path
from accounts import views


urlpatterns = [
    # Auth
    path("register", views.register_get, name="register_get"),
    path("register/submit", views.register_post, name="register_post"),
    path("login", views.login_get, name="login_get"),
    path("login/submit", views.login_post, name="login_post"),
    path("logout", views.logout_post, name="logout_post"),
    # Google OAuth2
    path("google/login", views.google_login_start, name="google_login_start"),
    path("google/callback", views.google_callback, name="google_callback"),
]

# Separate account URLs mounted under /account/
account_urlpatterns = [
    path("profile", views.profile_get, name="profile_get"),
    path("profile/update", views.profile_post, name="profile_post"),
    path("profile/upload-avatar", views.profile_upload_avatar_post, name="profile_upload_avatar_post"),
    path("change-password", views.change_password_post, name="change_password_post"),
]
