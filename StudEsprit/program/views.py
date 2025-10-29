from django.shortcuts import render, redirect
from django import forms
from . import services
from django.http import HttpRequest
from django.http import Http404
from django.conf import settings
from django.core.files.storage import default_storage
import tempfile


class NiveauForm(forms.Form):
    nom = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea, required=False)


class MatiereForm(forms.Form):
    nom = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea, required=False)
    niveau_id = forms.CharField(required=False)


class CourForm(forms.Form):
    nom = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea, required=False)
    coefficient = forms.FloatField(required=False)
    matiere_id = forms.CharField(required=False)
    courpdf = forms.FileField(required=False)


def niveaux_list(request):
    # Render the page with search form; the table content is loaded via HTMX
    return render(request, "program/niveaux_list.html")


def niveau_create(request):
    # Support normal navigation and HTMX partial replacement
    if request.method == "POST":
        form = NiveauForm(request.POST)
        if form.is_valid():
            services.create_niveau(form.cleaned_data["nom"], form.cleaned_data["description"])
            # If HTMX request, return the updated panel (table + empty form) with a success flag
            if request.headers.get("Hx-Request") == "true":
                return niveaux_panel(request, created=True)
            return redirect("niveaux_list")
    else:
        form = NiveauForm()
    return render(request, "program/niveau_form.html", {"form": form})


def niveaux_panel(request: HttpRequest, created: bool = False):
    # Panel includes the table and the create form. Accepts q/page/page_size like the partial.
    q = request.GET.get("q")
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size", "20"))
    except ValueError:
        page_size = 20
    skip = (page - 1) * page_size
    niveaux = services.list_niveaux(q=q, limit=page_size, skip=skip)
    form = NiveauForm()
    context = {"niveaux": niveaux, "form": form, "q": q or "", "page": page, "page_size": page_size, "created": created}
    return render(request, "program/_niveaux_panel.html", context)


def niveaux_partial(request: HttpRequest):
    q = request.GET.get("q")
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size", "20"))
    except ValueError:
        page_size = 20
    skip = (page - 1) * page_size
    niveaux = services.list_niveaux(q=q, limit=page_size, skip=skip)
    context = {"niveaux": niveaux, "q": q or "", "page": page, "page_size": page_size}
    return render(request, "program/_niveaux_table.html", context)


def niveau_delete(request: HttpRequest, nid=None):
    if request.method == "POST":
        services.delete_niveau(nid)
        return niveaux_panel(request)
    return niveaux_panel(request)


def niveau_edit(request: HttpRequest, nid=None):
    # GET returns form partial; POST updates and returns panel
    if request.method == "POST":
        # update
        data = {"nom": request.POST.get("nom"), "description": request.POST.get("description")}
        services.update_niveau(nid, data)
        return niveaux_panel(request)
    # GET: render partial form
    n = services.get_niveau(nid)
    if not n:
        raise Http404("Niveau not found")
    form = NiveauForm(initial={"nom": n.get("nom"), "description": n.get("description")})
    return render(request, "program/_niveaux_edit.html", {"form": form, "nid": nid})


# -- Matieres views
def matieres_list(request):
    niveaux = services.list_niveaux(limit=100)
    return render(request, "program/matieres_list.html", {"niveaux": niveaux})


def matiere_create(request):
    # Support normal navigation and HTMX partial replacement
    if request.method == "POST":
        form = MatiereForm(request.POST)
        if form.is_valid():
            services.create_matiere(form.cleaned_data["nom"], form.cleaned_data["description"], form.cleaned_data.get("niveau_id") or None)
            if request.headers.get("Hx-Request") == "true":
                return matieres_panel(request, created=True)
            return redirect("matieres_list")
    else:
        form = MatiereForm()
    # Provide niveaux for the standalone create page so the select shows options
    niveaux = services.list_niveaux(limit=200)
    return render(request, "program/matiere_form.html", {"form": form, "niveaux": niveaux})


def matieres_panel(request: HttpRequest, created: bool = False):
    q = request.GET.get("q")
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size", "20"))
    except ValueError:
        page_size = 20
    skip = (page - 1) * page_size
    niveau_id = request.GET.get("niveau_id")
    matieres = services.list_matieres(q=q, niveau_id=niveau_id, limit=page_size, skip=skip)
    niveaux = services.list_niveaux(limit=100)
    # annotate matieres with niveau names for display
    niveau_map = {n.get('id') or str(n.get('_id')): n.get('nom') for n in niveaux}
    for m in matieres:
        nid = m.get('niveau_id')
        m['niveau_nom'] = niveau_map.get(nid, '') if nid else ''
    form = MatiereForm()
    context = {"matieres": matieres, "niveaux": niveaux, "form": form, "q": q or "", "page": page, "page_size": page_size, "created": created}
    return render(request, "program/_matieres_panel.html", context)


def matieres_partial(request: HttpRequest):
    q = request.GET.get("q")
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size", "20"))
    except ValueError:
        page_size = 20
    skip = (page - 1) * page_size
    niveau_id = request.GET.get("niveau_id")
    matieres = services.list_matieres(q=q, niveau_id=niveau_id, limit=page_size, skip=skip)
    niveaux = services.list_niveaux(limit=100)
    niveau_map = {n.get('id') or str(n.get('_id')): n.get('nom') for n in niveaux}
    for m in matieres:
        nid = m.get('niveau_id')
        m['niveau_nom'] = niveau_map.get(nid, '') if nid else ''
    context = {"matieres": matieres, "q": q or "", "page": page, "page_size": page_size}
    return render(request, "program/_matieres_table.html", context)


def matiere_delete(request: HttpRequest, mid=None):
    if request.method == "POST":
        services.delete_matiere(mid)
        return matieres_panel(request)
    return matieres_panel(request)


def matiere_edit(request: HttpRequest, mid=None):
    if request.method == "POST":
        data = {"nom": request.POST.get("nom"), "description": request.POST.get("description"), "niveau_id": request.POST.get("niveau_id")}
        services.update_matiere(mid, data)
        return matieres_panel(request)
    m = services.get_matiere(mid)
    if not m:
        raise Http404("Matiere not found")
    niveaux = services.list_niveaux(limit=200)
    form = MatiereForm(initial={"nom": m.get("nom"), "description": m.get("description"), "niveau_id": m.get("niveau_id")})
    return render(request, "program/_matieres_edit.html", {"form": form, "mid": mid, "niveaux": niveaux})


# -- Cours views
def cours_list(request):
    matieres = services.list_matieres(limit=200)
    return render(request, "program/cours_list.html", {"matieres": matieres})


def cour_create(request):
    if request.method == "POST":
        form = CourForm(request.POST, request.FILES)
        if form.is_valid():
            coef = form.cleaned_data.get("coefficient") or 0
            # handle uploaded PDF (if any)
            courpdf_path = None
            uploaded = request.FILES.get('courpdf')
            # validate uploaded file (must be PDF and not too large)
            if uploaded:
                # basic mime check + fallback to extension
                content_type = getattr(uploaded, 'content_type', '') or ''
                max_size = 10 * 1024 * 1024  # 10 MB
                if not (('pdf' in content_type.lower()) or uploaded.name.lower().endswith('.pdf')):
                    form.add_error('courpdf', 'Le fichier doit être au format PDF.')
                elif uploaded.size and uploaded.size > max_size:
                    form.add_error('courpdf', 'Le fichier est trop volumineux (max 10 MB).')

            # validate matiere exists when provided
            mid = form.cleaned_data.get('matiere_id') or None
            if mid:
                if not services.get_matiere(mid):
                    form.add_error('matiere_id', 'Matière invalide.')

            # if any validation errors were added, re-render form with errors
            if form.errors:
                matieres = services.list_matieres(limit=200)
                return render(request, "program/cour_form.html", {"form": form, "matieres": matieres})

            if uploaded:
                from django.core.files.storage import default_storage
                from django.utils import timezone
                # sanitize filename (replace spaces)
                clean_name = uploaded.name.replace(' ', '_')
                stamp = int(timezone.now().timestamp() * 1000)
                filename = f"cours_pdfs/{stamp}_{clean_name}"
                saved = default_storage.save(filename, uploaded)
                # store public URL (resolves MEDIA_URL correctly)
                try:
                    courpdf_path = default_storage.url(saved)
                except Exception:
                    courpdf_path = saved

            services.create_cour(
                form.cleaned_data["nom"],
                form.cleaned_data.get("description", ""),
                float(coef),
                mid,
                courpdf_path,
            )
            if request.headers.get("Hx-Request") == "true":
                return cours_panel(request, created=True)
            return redirect("cours_list")
    else:
        form = CourForm()
    # Provide matieres for the standalone create page so the select shows options
    matieres = services.list_matieres(limit=200)
    return render(request, "program/cour_form.html", {"form": form, "matieres": matieres})


def cours_panel(request: HttpRequest, created: bool = False):
    q = request.GET.get("q")
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size", "20"))
    except ValueError:
        page_size = 20
    skip = (page - 1) * page_size
    matiere_id = request.GET.get("matiere_id")
    cours = services.list_cours(q=q, matiere_id=matiere_id, limit=page_size, skip=skip)
    matieres = services.list_matieres(limit=200)
    # annotate cours with matiere name
    mat_map = {m.get('id') or str(m.get('_id')): m.get('nom') for m in matieres}
    for c in cours:
        mid = c.get('matiere_id')
        c['matiere_nom'] = mat_map.get(mid, '') if mid else ''
    form = CourForm()
    context = {"cours": cours, "matieres": matieres, "form": form, "q": q or "", "page": page, "page_size": page_size, "created": created}
    return render(request, "program/_cours_panel.html", context)


def cours_partial(request: HttpRequest):
    q = request.GET.get("q")
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size", "20"))
    except ValueError:
        page_size = 20
    skip = (page - 1) * page_size
    matiere_id = request.GET.get("matiere_id")
    cours = services.list_cours(q=q, matiere_id=matiere_id, limit=page_size, skip=skip)
    matieres = services.list_matieres(limit=200)
    mat_map = {m.get('id') or str(m.get('_id')): m.get('nom') for m in matieres}
    for c in cours:
        mid = c.get('matiere_id')
        c['matiere_nom'] = mat_map.get(mid, '') if mid else ''
    context = {"cours": cours, "q": q or "", "page": page, "page_size": page_size}
    return render(request, "program/_cours_table.html", context)


def cour_delete(request: HttpRequest, cid=None):
    if request.method == "POST":
        services.delete_cour(cid)
        return cours_panel(request)
    return cours_panel(request)


def cour_edit(request: HttpRequest, cid=None):
    if request.method == "POST":
        # handle file upload if present
        courpdf_path = None
        uploaded = request.FILES.get('courpdf')
        if uploaded:
            from django.core.files.storage import default_storage
            from django.utils import timezone
            clean_name = uploaded.name.replace(' ', '_')
            stamp = int(timezone.now().timestamp() * 1000)
            filename = f"cours_pdfs/{stamp}_{clean_name}"
            saved = default_storage.save(filename, uploaded)
            try:
                courpdf_path = default_storage.url(saved)
            except Exception:
                courpdf_path = saved

        data = {"nom": request.POST.get("nom"), "description": request.POST.get("description"), "coefficient": float(request.POST.get("coefficient") or 0), "matiere_id": request.POST.get("matiere_id")}
        if courpdf_path:
            data["courpdf"] = courpdf_path
        services.update_cour(cid, data)
        return cours_panel(request)
    c = services.get_cour(cid)
    if not c:
        raise Http404("Cours not found")
    matieres = services.list_matieres(limit=200)
    form = CourForm(initial={"nom": c.get("nom"), "description": c.get("description"), "coefficient": c.get("coefficient"), "matiere_id": c.get("matiere_id"), "courpdf": c.get("courpdf")})
    return render(request, "program/_cours_edit.html", {"form": form, "cid": cid, "matieres": matieres})


def cour_generate_test(request: HttpRequest, cid=None):
    """Generate test questions for a course from its uploaded PDF.
    Returns an HTML partial (modal) with the generated questions and saves them to the course document.
    """
    c = services.get_cour(cid)
    if not c:
        raise Http404("Cours not found")
    pdf_src = c.get('courpdf')
    if not pdf_src:
        # return a small alert partial
        return render(request, "program/_cours_tests_modal.html", {"error": "Aucun PDF associé à ce cours.", "questions": []})

    # prepare a temp file path for generator
    tmp_path = None
    try:
        # import generator and requests lazily so Django can start even if optional deps are missing
        try:
            import requests
        except Exception:
            requests = None
        try:
            from ml_service import generator as ml_generator
        except ModuleNotFoundError as e:
            return render(request, "program/_cours_tests_modal.html", {"error": f"Le module de génération n'est pas disponible: {e}. Installez les dépendances ml_service.", "questions": []})

        # If the stored path is an absolute http URL, fetch it
        if isinstance(pdf_src, str) and pdf_src.startswith('http'):
            if not requests:
                return render(request, "program/_cours_tests_modal.html", {"error": "Le paquet 'requests' n'est pas installé sur le serveur.", "questions": []})
            r = requests.get(pdf_src)
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
                tf.write(r.content)
                tmp_path = tf.name
        else:
            # assume it's a MEDIA_URL-based path or a storage path
            rel = pdf_src
            # if it starts with MEDIA_URL, strip it
            if pdf_src.startswith(settings.MEDIA_URL):
                rel = pdf_src[len(settings.MEDIA_URL):]
                rel = rel.lstrip('/')
            # open via default_storage and write to temp
            with default_storage.open(rel, 'rb') as fh, tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
                tf.write(fh.read())
                tmp_path = tf.name

        # generate questions
        questions = ml_generator.generate_questions_from_text(tmp_path, num_questions=8)
        # save generated tests into the course document
        services.update_cour(cid, {'generated_tests': questions})
        return render(request, "program/_cours_tests_modal.html", {"questions": questions, "cid": cid})
    except Exception as e:
        return render(request, "program/_cours_tests_modal.html", {"error": str(e), "questions": []})
    finally:
        if tmp_path:
            try:
                import os
                os.remove(tmp_path)
            except Exception:
                pass


def cour_view_test(request: HttpRequest, cid=None):
    # Show stored generated tests for the course (if any)
    c = services.get_cour(cid)
    if not c:
        raise Http404("Cours not found")
    questions = c.get('generated_tests') or []
    return render(request, "program/_cours_tests_modal.html", {"questions": questions, "cid": cid})


def cour_generate_summary(request: HttpRequest, cid=None):
    """Generate an extractive summary for a course from its uploaded PDF.
    Returns an HTML partial (modal) with the generated summary and saves it to the course document.
    """
    c = services.get_cour(cid)
    if not c:
        raise Http404("Cours not found")
    pdf_src = c.get('courpdf')
    if not pdf_src:
        return render(request, "program/_cours_summary_modal.html", {"error": "Aucun PDF associé à ce cours.", "summary": None})

    tmp_path = None
    try:
        try:
            import requests
        except Exception:
            requests = None
        try:
            from ml_service import generator as ml_generator
        except ModuleNotFoundError as e:
            return render(request, "program/_cours_summary_modal.html", {"error": f"Le module de génération n'est pas disponible: {e}. Installez les dépendances ml_service.", "summary": None})

        # fetch or read PDF into temp file
        if isinstance(pdf_src, str) and pdf_src.startswith('http'):
            if not requests:
                return render(request, "program/_cours_summary_modal.html", {"error": "Le paquet 'requests' n'est pas installé sur le serveur.", "summary": None})
            r = requests.get(pdf_src)
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
                tf.write(r.content)
                tmp_path = tf.name
        else:
            rel = pdf_src
            if pdf_src.startswith(settings.MEDIA_URL):
                rel = pdf_src[len(settings.MEDIA_URL):]
                rel = rel.lstrip('/')
            with default_storage.open(rel, 'rb') as fh, tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
                tf.write(fh.read())
                tmp_path = tf.name

        summary = ml_generator.generate_summary_from_text(tmp_path, num_sentences=5)
        # persist summary into course doc
        services.update_cour(cid, {'generated_summary': summary})
        return render(request, "program/_cours_summary_modal.html", {"summary": summary, "cid": cid})
    except Exception as e:
        return render(request, "program/_cours_summary_modal.html", {"error": str(e), "summary": None})
    finally:
        if tmp_path:
            try:
                import os
                os.remove(tmp_path)
            except Exception:
                pass


def cour_view_summary(request: HttpRequest, cid=None):
    c = services.get_cour(cid)
    if not c:
        raise Http404("Cours not found")
    summary = c.get('generated_summary') or None
    return render(request, "program/_cours_summary_modal.html", {"summary": summary, "cid": cid})
