from django.urls import path
from . import views

urlpatterns = [
    path("niveaux/", views.niveaux_list, name="niveaux_list"),
    path("niveaux/partial", views.niveaux_partial, name="niveaux_partial"),
    path("niveaux/panel", views.niveaux_panel, name="niveaux_panel"),
    path("niveaux/create/", views.niveau_create, name="niveau_create"),
    path("niveaux/delete/<str:nid>/", views.niveau_delete, name="niveau_delete"),
    path("niveaux/edit/<str:nid>/", views.niveau_edit, name="niveau_edit"),
    # Matieres
    path("matieres/", views.matieres_list, name="matieres_list"),
    path("matieres/partial", views.matieres_partial, name="matieres_partial"),
    path("matieres/panel", views.matieres_panel, name="matieres_panel"),
    path("matieres/create/", views.matiere_create, name="matiere_create"),
    path("matieres/delete/<str:mid>/", views.matiere_delete, name="matiere_delete"),
    path("matieres/edit/<str:mid>/", views.matiere_edit, name="matiere_edit"),
    # Cours
    path("cours/", views.cours_list, name="cours_list"),
    path("cours/partial", views.cours_partial, name="cours_partial"),
    path("cours/panel", views.cours_panel, name="cours_panel"),
    path("cours/create/", views.cour_create, name="cour_create"),
    path("cours/delete/<str:cid>/", views.cour_delete, name="cour_delete"),
    path("cours/edit/<str:cid>/", views.cour_edit, name="cour_edit"),
    path("cours/generate_test/<str:cid>/", views.cour_generate_test, name="cour_generate_test"),
    path("cours/view_test/<str:cid>/", views.cour_view_test, name="cour_view_test"),
    path("cours/generate_summary/<str:cid>/", views.cour_generate_summary, name="cour_generate_summary"),
    path("cours/view_summary/<str:cid>/", views.cour_view_summary, name="cour_view_summary"),
    # Inline HTMX endpoints for public view swapping
    path("cours/view_test/inline/<str:cid>/", views.cour_view_test_inline, name="cour_view_test_inline"),
    path("cours/view_summary/inline/<str:cid>/", views.cour_view_summary_inline, name="cour_view_summary_inline"),
    path("cours/pdf_partial/<str:cid>/", views.cour_pdf_partial, name="cour_pdf_partial"),
    # Public-facing program pages (niveaux -> matieres -> cours -> cours detail)
    path("public/program/", views.public_program_index, name="program_public_index"),
    path("public/program/niveau/<str:niveau_id>/", views.public_niveau, name="program_public_niveau"),
    path("public/program/matiere/<str:matiere_id>/", views.public_matiere, name="program_public_matiere"),
    path("public/program/cour/<str:cour_id>/", views.public_cour_detail, name="program_public_cour_detail"),
    path("public/program/niveau/<str:niveau_id>/generate_plan/pre/", views.public_generate_plan_pre, name="program_public_generate_plan_pre"),
    path("public/program/niveau/<str:niveau_id>/generate_plan/", views.public_generate_plan, name="program_public_generate_plan"),
    # Inline HTMX endpoints to load test/summary/pdf into the course detail page
    path("cours/view_test_inline/<str:cid>/", views.cour_view_test_inline, name="cour_view_test_inline"),
    path("cours/view_summary_inline/<str:cid>/", views.cour_view_summary_inline, name="cour_view_summary_inline"),
    path("cours/pdf_partial/<str:cid>/", views.cour_pdf_partial, name="cour_pdf_partial"),
]
