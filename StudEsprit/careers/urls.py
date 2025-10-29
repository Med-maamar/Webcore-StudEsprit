from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApplicationViewSet,
    CVProfilePageView,
    CoverLetterHTMXView,
    CoverLetterView,
    CoverLetterSaveView,
    CvGapAnalysisView,
    InterviewPrepView,
    OpportunityApplyView,
    OpportunityDeleteView,
    OpportunityEditView,
    OpportunityDetailPageView,
    OpportunityListPageView,
    OpportunityCreateView,
    OpportunityViewSet,
    ProfileGapAnalysisView,
    profile_api_view,
    MyApplicationsPageView,
    InterviewPrepHTMLView,
    InterviewPrepDeleteView,
    # Admin
    AdminApplicationsListView,
    AdminApplicationDetailView,
    AdminApplicationInterviewView,
    AdminInterviewUpdateView,
    AdminInterviewDeleteView,
    AdminApplicationValidateView,
)


router = DefaultRouter(trailing_slash=True)
router.register(r"opportunities", OpportunityViewSet, basename="careers-opportunity")
router.register(r"applications", ApplicationViewSet, basename="careers-application")


api_patterns = [
    path("", include(router.urls)),
    path("profile/", profile_api_view, name="careers-profile"),
    path("ai/cv-gap-analysis/", CvGapAnalysisView.as_view(), name="careers-ai-cv-gap"),
    path("ai/cover-letter/", CoverLetterView.as_view(), name="careers-ai-cover"),
    path("ai/cover-letter/save/", CoverLetterSaveView.as_view(), name="careers-ai-cover-save"),
    path("ai/interview-prep/", InterviewPrepView.as_view(), name="careers-ai-interview"),
]


app_name = "careers"


urlpatterns = [
    path("api/", include((api_patterns, app_name))),
    path("careers/opportunities/", OpportunityListPageView.as_view(), name="opportunity-list"),
    path("careers/applications/", MyApplicationsPageView.as_view(), name="my-applications"),
    path("careers/opportunities/create/", OpportunityCreateView.as_view(), name="opportunity-create"),
    path("careers/opportunities/<str:pk>/", OpportunityDetailPageView.as_view(), name="opportunity-detail"),
    path("careers/opportunities/<str:pk>/edit/", OpportunityEditView.as_view(), name="opportunity-edit"),
    path("careers/opportunities/<str:pk>/delete/", OpportunityDeleteView.as_view(), name="opportunity-delete"),
    path("careers/opportunities/<str:pk>/apply/", OpportunityApplyView.as_view(), name="opportunity-apply"),
    path(
        "careers/opportunities/<str:pk>/cover-letter/",
        CoverLetterHTMXView.as_view(),
        name="opportunity-cover-letter",
    ),
    path("careers/applications/<str:pk>/interview-prep/", InterviewPrepHTMLView.as_view(), name="application-interview-prep"),
    path("careers/applications/<str:pk>/interview-prep/delete/", InterviewPrepDeleteView.as_view(), name="application-interview-prep-delete"),
    path("careers/profile/", CVProfilePageView.as_view(), name="profile"),
    path("careers/profile/analyze/", ProfileGapAnalysisView.as_view(), name="profile-gap"),
    # Admin careers
    path("admin/careers/applications/", AdminApplicationsListView.as_view(), name="admin-applications"),
    path("admin/careers/applications/<str:pk>/", AdminApplicationDetailView.as_view(), name="admin-application-detail"),
    path("admin/careers/applications/<str:pk>/interview/", AdminApplicationInterviewView.as_view(), name="admin-application-interview"),
    path("admin/careers/interviews/<str:pk>/", AdminInterviewUpdateView.as_view(), name="admin-interview-update"),
    path("admin/careers/interviews/<str:pk>/delete/", AdminInterviewDeleteView.as_view(), name="admin-interview-delete"),
    path("admin/careers/applications/<str:pk>/validate/", AdminApplicationValidateView.as_view(), name="admin-application-validate"),
]
