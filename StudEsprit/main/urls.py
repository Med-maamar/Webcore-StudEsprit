# main/urls.py
from django.urls import include, path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from core.views import coming_soon, home
from django.views.generic import RedirectView
from careers.views import (
    AdminApplicationsListView,
    AdminApplicationDetailView,
    AdminApplicationInterviewView,
    AdminInterviewUpdateView,
    AdminInterviewDeleteView,
    AdminApplicationValidateView,
)
from accounts.urls import account_urlpatterns

urlpatterns = [
    # Custom admin (careers) must come BEFORE Django admin catch-all
    path("admin/careers/applications/", AdminApplicationsListView.as_view(), name="careers-admin-applications"),
    path("admin/careers/applications/<str:pk>/", AdminApplicationDetailView.as_view(), name="careers-admin-application-detail"),
    path("admin/careers/applications/<str:pk>/interview/", AdminApplicationInterviewView.as_view(), name="careers-admin-application-interview"),
    path("admin/careers/interviews/<str:pk>/", AdminInterviewUpdateView.as_view(), name="careers-admin-interview-update"),
    path("admin/careers/interviews/<str:pk>/delete/", AdminInterviewDeleteView.as_view(), name="careers-admin-interview-delete"),
    path("admin/careers/applications/<str:pk>/validate/", AdminApplicationValidateView.as_view(), name="careers-admin-application-validate"),

    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("auth/", include("accounts.urls")),  # Login: /auth/login/
    path("account/", include((account_urlpatterns, "accounts"), namespace="account")),
    path("dashboard/", include("dashboard.urls")),
    path("library/", include("library.urls")),
    path("", include("careers.urls")),
    path("services/", RedirectView.as_view(pattern_name="careers:opportunity-list", permanent=False), name="services"),
    path("courses/", coming_soon, name="courses"),
    
    # ONLY ONE events/ — NO DUPLICATES
path("evenement/", include("evenement.urls")),
path("events/", include("evenement.urls")),

    path("shop/", coming_soon, name="shop"),
    path("program/", include("program.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)