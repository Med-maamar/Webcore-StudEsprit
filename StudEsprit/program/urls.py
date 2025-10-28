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
]
