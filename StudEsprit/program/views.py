from django.shortcuts import render, redirect
from django import forms
from . import services
from django.http import HttpRequest
from django.http import Http404, JsonResponse
from django.conf import settings
from django.core.files.storage import default_storage
from django.urls import reverse
import tempfile
import json
import random
from typing import Any, Dict
from ml_service import average_analyzer
from django.views.decorators.csrf import csrf_exempt
from ml_service import generate_subjects_app as gen_app


class NiveauForm(forms.Form):
    nom = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea, required=False)


class MatiereForm(forms.Form):
    nom = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea, required=False)
    niveau_id = forms.CharField(required=False)
    coefficient = forms.FloatField(required=False)


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
    # If this is an HTMX request (e.g., loading inside a modal or panel),
    # return the partial form that does not extend the base layout to avoid
    # duplicating the whole page inside the current view.
    if request.headers.get("Hx-Request") == "true":
        return render(request, "program/_niveaux_form.html", {"form": form})
    return render(request, "program/niveau_form.html", {"form": form})


def niveaux_panel(request: HttpRequest, created: bool = False):
    # Panel includes the table and the create form. Accepts q/page/page_size like the partial.
    q = request.GET.get("q")
    try:
        page = int(request.GET.get("page", "1"))
    except Exception:
        page = 1
    try:
        page_size = int(request.GET.get("page_size", "20"))
    except Exception:
        page_size = 20
    skip = max(0, (page - 1) * page_size)
    # get total count to compute pages
    try:
        total_count = services.count_niveaux(q=q)
    except Exception:
        total_count = 0
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count is not None else 1
    # clamp page
    if page > total_pages:
        page = total_pages
    skip = max(0, (page - 1) * page_size)
    niveaux = services.list_niveaux(q=q, limit=page_size, skip=skip)
    panel_url = reverse('niveaux_panel')
    return render(request, "program/niveaux_panel.html", {"niveaux": niveaux, "created": created, "q": q or "", "page": page, "page_size": page_size, "panel_url": panel_url, "total_count": total_count, "total_pages": total_pages})


def niveaux_partial(request: HttpRequest):
    """Backward-compatible wrapper used by urls.py for the HTMX partial endpoint.
    Previously the view was named `niveaux_partial`; code now delegates to
    `niveaux_panel` which returns the same partial content.
    """
    return niveaux_panel(request)


def niveau_delete(request: HttpRequest, nid=None):
    """Delete a niveau and return the updated panel (POST) or panel otherwise."""
    if request.method == 'POST':
        try:
            services.delete_niveau(nid)
        except Exception:
            pass
        return niveaux_panel(request)
    return niveaux_panel(request)


def niveau_edit(request: HttpRequest, nid=None):
    n = services.get_niveau(nid)
    if not n:
        raise Http404("Niveau not found")
    if request.method == 'POST':
        form = NiveauForm(request.POST)
        if form.is_valid():
            services.update_niveau(nid, {"nom": form.cleaned_data["nom"], "description": form.cleaned_data.get("description", "")})
            if request.headers.get("Hx-Request") == "true":
                return niveaux_panel(request, created=True)
            return redirect("niveaux_list")
    else:
        form = NiveauForm(initial={"nom": n.get("nom"), "description": n.get("description")})
    # For edit GETs, we render a lightweight modal partial when called via HTMX
    # to prevent embedding the full base template inside the current page.
    if request.headers.get("Hx-Request") == "true":
        return render(request, "program/_niveaux_edit.html", {"form": form, "nid": nid})
    return render(request, "program/niveau_form.html", {"form": form, "nid": nid})


def matieres_list(request: HttpRequest):
    q = request.GET.get('q')
    try:
        matieres = services.list_matieres(q=q, limit=200)
    except Exception:
        matieres = services.list_matieres(limit=200)
    # also provide niveaux for the filter select
    try:
        niveaux = services.list_niveaux(limit=200)
    except Exception:
        niveaux = services.list_niveaux()
    return render(request, "program/matieres_list.html", {"matieres": matieres, "q": q or "", "niveaux": niveaux, "niveau_id": request.GET.get('niveau_id', '')})


def matieres_partial(request: HttpRequest):
    q = request.GET.get('q')
    try:
        matieres = services.list_matieres(q=q, limit=200)
    except Exception:
        matieres = services.list_matieres(limit=200)
    # enrich matieres with niveau name for display
    enriched = []
    for m in matieres:
        m_copy = dict(m)
        try:
            nid = m.get('niveau_id')
            niveau = services.get_niveau(nid) if nid else None
            m_copy['niveau_nom'] = niveau.get('nom') if niveau else ''
        except Exception:
            m_copy['niveau_nom'] = ''
        enriched.append(m_copy)
    return render(request, "program/_matieres_table.html", {"matieres": enriched, "q": q or ""})


def matieres_panel(request: HttpRequest, created: bool = False):
    import traceback as _tb
    try:
        q = request.GET.get('q')
        try:
            page = int(request.GET.get('page', '1'))
        except Exception:
            page = 1
        try:
            page_size = int(request.GET.get('page_size', '20'))
        except Exception:
            page_size = 20
        skip = max(0, (page - 1) * page_size)
        # total count for pagination
        try:
            total_count = services.count_matieres(q=q, niveau_id=request.GET.get('niveau_id'))
        except Exception:
            total_count = 0
        total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count is not None else 1
        if page > total_pages:
            page = total_pages
            skip = max(0, (page - 1) * page_size)
        matieres = services.list_matieres(q=q, limit=page_size, skip=skip)
        # attach niveau names for display in the table
        enriched = []
        for m in matieres:
            m_copy = dict(m)
            try:
                nid = m.get('niveau_id')
                niveau = services.get_niveau(nid) if nid else None
                m_copy['niveau_nom'] = niveau.get('nom') if niveau else ''
            except Exception:
                m_copy['niveau_nom'] = ''
            enriched.append(m_copy)

        # also provide niveaux for the generator modal
        try:
            niveaux = services.list_niveaux(limit=200)
        except Exception:
            niveaux = services.list_niveaux()
        panel_url = reverse('matieres_panel')
        return render(request, "program/matieres_panel.html", {"matieres": enriched, "created": created, "q": q or "", "page": page, "page_size": page_size, "panel_url": panel_url, "niveaux": niveaux, "total_count": total_count, "total_pages": total_pages})
    except Exception as e:
        tb = _tb.format_exc()
        # Render a small error partial so HTMX receives HTML instead of 500
        return render(request, "program/_panel_error.html", {"error": str(e), "trace": tb})


def matieres_json(request):
    """Return matieres for a given niveau as JSON. Used by admin modal as a fallback
    when the external generator returns no results.

    Query params:
      - niveau_id: str (optional) : DB id of niveau to filter matieres. If omitted, returns recent matieres.
    """
    try:
        niveau_id = request.GET.get("niveau_id")
        if niveau_id:
            matieres = services.list_matieres(niveau_id=niveau_id, limit=200)
        else:
            matieres = services.list_matieres(limit=200)
        # serialize minimal fields for the modal
        out = []
        for m in matieres:
            out.append({
                "nom": m.get("nom"),
                "description": m.get("description", ""),
                "coefficient": m.get("coefficient", 1),
                "niveau_id": str(m.get("niveau_id")) if m.get("niveau_id") else None,
            })
        return JsonResponse({"ok": True, "count": len(out), "matieres": out})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
@csrf_exempt
def generate_matieres_local(request: HttpRequest):
    """Proxy endpoint that runs the local generator logic inside Django so the
    generator appears under the same origin (no CORS) and can be called at
    /program/api/generate_matieres/.

    This view is intentionally csrf_exempt because the previous frontend calls
    the external generator without sending a CSRF token. If you prefer stricter
    checks, remove the decorator and ensure the client includes the CSRF token.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    niveau = (payload.get('niveau') or '').strip()
    try:
        count = int(payload.get('count') or 6)
    except Exception:
        count = 6
    seed = payload.get('shuffle_seed')

    data = gen_app.load_dataset()
    if niveau:
        filtered = [r for r in data if r.get('niveau_education', '').lower() == niveau.lower()]
    else:
        filtered = data

    if seed is not None:
        try:
            random.seed(int(seed))
        except Exception:
            pass

    if len(filtered) >= count:
        sample = random.sample(filtered, count)
    else:
        sample = filtered[:]
        remaining = [r for r in data if r not in filtered]
        need = max(0, count - len(sample))
        if need > 0 and remaining:
            sample += random.sample(remaining, min(need, len(remaining)))

    for s in sample:
        if niveau:
            s['suggested_for_niveau'] = niveau

    return JsonResponse({'ok': True, 'count': len(sample), 'matieres': sample})


def matiere_create(request: HttpRequest):
    if request.method == 'POST':
        # Support both form-encoded submissions and JSON posts from the generator modal
        if request.content_type and 'application/json' in request.content_type:
            try:
                import json
                payload = json.loads(request.body.decode('utf-8') or '{}')
            except Exception:
                payload = {}
            nom = payload.get('nom')
            desc = payload.get('description', '')
            niveau_id = payload.get('niveau_education') or payload.get('niveau_id')
            coef = payload.get('coefficient')
            # some payloads may give coef as string
            try:
                coef = float(coef) if coef is not None else 0
            except Exception:
                coef = 0
            if nom:
                created = services.create_matiere(nom, desc, niveau_id, coefficient=coef)
                # build a minimal serializable representation to return
                try:
                    created_id = created.get('id') or str(created.get('_id'))
                except Exception:
                    created_id = str(created)
                created_doc = {
                    'id': created_id,
                    'nom': created.get('nom'),
                    'description': created.get('description', ''),
                    'coefficient': created.get('coefficient', 0),
                    'niveau_id': created.get('niveau_id')
                }
                # return JSON success for the modal
                from django.http import JsonResponse
                return JsonResponse({'ok': True, 'created_id': created_id, 'created': created_doc}, status=201)
            else:
                from django.http import JsonResponse
                return JsonResponse({'ok': False, 'error': 'nom missing'}, status=400)
        else:
            form = MatiereForm(request.POST)
            if form.is_valid():
                nom = form.cleaned_data["nom"]
                desc = form.cleaned_data.get("description", "")
                niveau_id = form.cleaned_data.get("niveau_id")
                coef = form.cleaned_data.get("coefficient")
                services.create_matiere(nom, desc, niveau_id, coefficient=coef)
                if request.headers.get("Hx-Request") == "true":
                    return matieres_panel(request, created=True)
                return redirect("matieres_list")
    else:
        form = MatiereForm()
    niveaux = services.list_niveaux(limit=200)
    # Serve a partial (no base layout) when requested via HTMX to avoid
    # duplicating the overall page structure inside the current interface.
    if request.headers.get("Hx-Request") == "true":
        return render(request, "program/_matieres_form.html", {"form": form, "niveaux": niveaux})
    return render(request, "program/matiere_form.html", {"form": form, "niveaux": niveaux})


def matiere_delete(request: HttpRequest, mid=None):
    if request.method == 'POST':
        try:
            services.delete_matiere(mid)
        except Exception:
            pass
        return matieres_panel(request)
    return matieres_panel(request)


def matiere_edit(request: HttpRequest, mid=None):
    m = services.get_matiere(mid)
    if not m:
        raise Http404("Matière not found")
    if request.method == 'POST':
        form = MatiereForm(request.POST)
        if form.is_valid():
            data = {"nom": form.cleaned_data.get("nom"), "description": form.cleaned_data.get("description", ""), "coefficient": form.cleaned_data.get("coefficient")}
            services.update_matiere(mid, data)
            if request.headers.get("Hx-Request") == "true":
                return matieres_panel(request, created=True)
            return redirect("matieres_list")
    else:
        form = MatiereForm(initial={"nom": m.get("nom"), "description": m.get("description"), "niveau_id": m.get("niveau_id"), "coefficient": m.get("coefficient")})
    niveaux = services.list_niveaux(limit=200)
    # When opened via HTMX (edit button inside the panel), return the modal
    # partial instead of the full page to avoid duplicated layout rendering.
    if request.headers.get("Hx-Request") == "true":
        return render(request, "program/_matieres_edit.html", {"form": form, "mid": mid, "niveaux": niveaux})
    return render(request, "program/matiere_form.html", {"form": form, "mid": mid, "niveaux": niveaux})


def cours_list(request: HttpRequest):
    q = request.GET.get('q')
    try:
        cours = services.list_cours(q=q, limit=200)
    except Exception:
        cours = services.list_cours(limit=200)
    return render(request, "program/cours_list.html", {"cours": cours, "q": q or ""})


def cour_create(request: HttpRequest):
    if request.method == 'POST':
        form = CourForm(request.POST, request.FILES)
        if form.is_valid():
            nom = form.cleaned_data.get("nom")
            desc = form.cleaned_data.get("description")
            coef = float(form.cleaned_data.get("coefficient") or 0)
            mid = form.cleaned_data.get("matiere_id")
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
            services.create_cour(nom, desc, coef, mid, courpdf=courpdf_path)
            if request.headers.get("Hx-Request") == "true":
                return cours_panel(request, created=True)
            return redirect("cours_list")
    else:
        form = CourForm()
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
    # total count for pagination
    try:
        total_count = services.count_cours(q=q, matiere_id=matiere_id)
    except Exception:
        total_count = 0
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count is not None else 1
    if page > total_pages:
        page = total_pages
        skip = (page - 1) * page_size
    cours = services.list_cours(q=q, matiere_id=matiere_id, limit=page_size, skip=skip)
    matieres = services.list_matieres(limit=200)
    # annotate cours with matiere name
    mat_map = {m.get('id') or str(m.get('_id')): m.get('nom') for m in matieres}
    for c in cours:
        mid = c.get('matiere_id')
        c['matiere_nom'] = mat_map.get(mid, '') if mid else ''
    form = CourForm()
    panel_url = reverse('cours_panel')
    context = {"cours": cours, "matieres": matieres, "form": form, "q": q or "", "page": page, "page_size": page_size, "created": created, "panel_url": panel_url, "total_count": total_count, "total_pages": total_pages}
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
    try:
        total_count = services.count_cours(q=q, matiere_id=matiere_id)
    except Exception:
        total_count = 0
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count is not None else 1
    if page > total_pages:
        page = total_pages
        skip = (page - 1) * page_size
    cours = services.list_cours(q=q, matiere_id=matiere_id, limit=page_size, skip=skip)
    matieres = services.list_matieres(limit=200)
    mat_map = {m.get('id') or str(m.get('_id')): m.get('nom') for m in matieres}
    for c in cours:
        mid = c.get('matiere_id')
        c['matiere_nom'] = mat_map.get(mid, '') if mid else ''
    context = {"cours": cours, "q": q or "", "page": page, "page_size": page_size, "total_count": total_count, "total_pages": total_pages}
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


# ----- Public-facing views (simplified cards/list navigation)
def public_program_index(request):
    """Show all niveaux as cards. Each card shows the niveau name (bold) and a short description."""
    q = request.GET.get('q')
    try:
        niveaux = services.list_niveaux(q=q, limit=200)
    except Exception:
        niveaux = services.list_niveaux(limit=200)
    return render(request, "program/public_index.html", {"niveaux": niveaux, "q": q or ""})


def public_niveau(request, niveau_id=None):
    """Show matieres for a given niveau as cards. If niveau not found, show 404."""
    n = services.get_niveau(niveau_id)
    if not n:
        raise Http404("Niveau not found")
    # ensure the niveau dict exposes a string id for URL reversing in templates
    try:
        if not n.get('id'):
            n['id'] = str(n.get('_id') or niveau_id)
        else:
            n['id'] = str(n.get('id'))
    except Exception:
        n['id'] = str(niveau_id or '')
    q = request.GET.get('q')
    coef = request.GET.get('coef')
    try:
        matieres = services.list_matieres(q=q, niveau_id=niveau_id, limit=200)
    except Exception:
        matieres = services.list_matieres(niveau_id=niveau_id, limit=200)

    # filter by coefficient if provided
    if coef not in (None, ''):
        try:
            coef_val = float(coef)
            matieres = [m for m in matieres if m.get('coefficient') is not None and float(m.get('coefficient')) == coef_val]
        except Exception:
            # if coef is not a valid number, do not filter
            pass

    return render(request, "program/public_niveau.html", {"niveau": n, "matieres": matieres, "q": q or "", "coef": coef or ""})


def public_matiere(request, matiere_id=None):
    """Show cours list for a matiere. Each course is a link to the course detail page (names only)."""
    m = services.get_matiere(matiere_id)
    if not m:
        raise Http404("Matière not found")
    # ensure the matiere dict exposes a string id for URL reversing in templates
    try:
        if not m.get('id'):
            m['id'] = str(m.get('_id') or matiere_id)
        else:
            m['id'] = str(m.get('id'))
    except Exception:
        m['id'] = str(matiere_id or '')
    q = request.GET.get('q')
    has_test = request.GET.get('has_test')
    has_summary = request.GET.get('has_summary')
    try:
        cours = services.list_cours(q=q, matiere_id=matiere_id, limit=500)
    except Exception:
        cours = services.list_cours(matiere_id=matiere_id, limit=500)

    # filter courses by presence of generated tests / summaries
    if has_test in ('1', 'true', 'on'):
        cours = [c for c in cours if c.get('generated_tests')]
    if has_summary in ('1', 'true', 'on'):
        cours = [c for c in cours if c.get('generated_summary')]

    return render(request, "program/public_matiere.html", {"matiere": m, "cours": cours, "q": q or "", "has_test": has_test or "", "has_summary": has_summary or ""})


def public_cour_detail(request, cour_id=None):
    """Show course detail: embedded PDF (if available) and links/buttons for test and summary.

    Uses existing endpoints for generate/view test and summary so the UI can open modals or new pages.
    """
    c = services.get_cour(cour_id)
    if not c:
        raise Http404("Cours not found")
    # ensure the course dict exposes a string id for URL reversing in templates
    try:
        # prefer existing 'id' field if present, otherwise use _id
        if not c.get('id'):
            c['id'] = str(c.get('_id') or cour_id)
        else:
            c['id'] = str(c.get('id'))
    except Exception:
        c['id'] = str(cour_id or '')

    # prepare simple values for template
    tests_exist = bool(c.get('generated_tests'))
    summary = c.get('generated_summary')

    # Try to resolve the matiere object (for display) and expose a matiere name on the course dict
    matiere = None
    try:
        mid = c.get('matiere_id')
        if mid:
            matiere = services.get_matiere(mid)
            if matiere:
                c['matiere_nom'] = matiere.get('nom')
    except Exception:
        # non-fatal: leave matiere as None
        matiere = None

    # Support a 'chapter' display field. If a dedicated 'chapter' exists use it,
    # otherwise fall back to the legacy 'coefficient' value (this keeps backwards
    # compatibility with existing data where coefficient may have been used).
    chapter = c.get('chapter')
    if chapter is None:
        coef = c.get('coefficient')
        if coef is not None:
            try:
                # try convert floats like 1.0 to int 1 for cleaner display
                chapter = int(coef)
            except Exception:
                chapter = coef
        else:
            chapter = None
    c['chapter'] = chapter

    # provide both 'cour' and alias 'c' for templates that use either variable name
    return render(request, "program/public_cour_detail.html", {"cour": c, "c": c, "tests_exist": tests_exist, "summary": summary, "matiere": matiere})


def public_generate_plan(request: HttpRequest, niveau_id=None):
    """Generate a study plan for a niveau and return an HTML partial for HTMX replacement.

    Accepts optional POST params:
    - unavailable: JSON mapping day -> list of hours to avoid, e.g. {"Mon": [12,13], "Sun": [10]}
    - total_hours_per_week: integer
    """
    try:
        n = services.get_niveau(niveau_id)
        if not n:
            raise Http404("Niveau not found")

        # collect matieres for this niveau
        try:
            matieres = services.list_matieres(niveau_id=niveau_id, limit=200)
        except Exception:
            matieres = services.list_matieres(niveau_id=niveau_id)

        # build simple list for generator
        gen_matieres = []
        for m in matieres:
            gen_matieres.append({"nom": m.get('nom'), "coefficient": m.get('coefficient')})

        # parse optional params
        unavailable = {}
        total_hours = 20
        if request.method == 'POST':
            # allow JSON body or form fields
            try:
                payload = json.loads(request.body.decode('utf-8')) if request.body else {}
            except Exception:
                payload = {}
            # merge form-encoded if present
            if not payload:
                payload = {k: request.POST.get(k) for k in request.POST}
            # parse unavailable
            u = payload.get('unavailable')
            if isinstance(u, str):
                try:
                    unavailable = json.loads(u)
                except Exception:
                    unavailable = {}
            elif isinstance(u, dict):
                unavailable = u
            # parse total hours
            try:
                total_hours = int(payload.get('total_hours_per_week') or payload.get('total_hours') or total_hours)
            except Exception:
                total_hours = total_hours
        else:
            # GET: allow query params
            try:
                total_hours = int(request.GET.get('total_hours_per_week') or total_hours)
            except Exception:
                total_hours = total_hours

        # normalize plan for template: build list of (day, slots)
        plan_days = []
        plan_summary = []
        enriched_plan_days = []
        # call local generator (fallback to a simple built-in generator on import error)
        plan = None
        try:
            from ml_service.plan_generator import generate_plan
            plan = generate_plan(gen_matieres, unavailable=unavailable, total_hours_per_week=total_hours)
        except Exception:
            # local fallback generator: distributes hours proportionally and fills hourly slots
            def _local_generate(gen_matieres, unavailable, total_hours_per_week):
                week_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                hours = list(range(8, 21))
                # numeric coefficients
                numeric = []
                for m in gen_matieres:
                    try:
                        numeric.append(float(m.get('coefficient') or 0))
                    except Exception:
                        numeric.append(0.0)
                total_coef = sum(numeric) or 1.0
                # allocate integer hours per matiere
                alloc = []
                for n in numeric:
                    h = int(round(total_hours_per_week * (n / total_coef))) if total_coef > 0 else 0
                    alloc.append(max(1, h) if n > 0 else 0)
                # adjust rounding differences
                s = sum(alloc)
                if s != total_hours_per_week and alloc:
                    diff = total_hours_per_week - s
                    try:
                        idx = numeric.index(max(numeric))
                    except Exception:
                        idx = 0
                    alloc[idx] = max(0, alloc[idx] + diff)

                # build assignment list
                assignments = []
                for i, a in enumerate(alloc):
                    assignments.extend([i] * a)

                slots = {d: [] for d in week_days}
                ai = 0
                for d in week_days:
                    day_unavail = unavailable.get(d, []) if isinstance(unavailable, dict) else []
                    for h in hours:
                        if h in day_unavail:
                            slots[d].append({"hour": h, "unavailable": True})
                            continue
                        if ai < len(assignments):
                            slots[d].append({"hour": h, "matiere_idx": assignments[ai]})
                            ai += 1
                        else:
                            slots[d].append({"hour": h})

                # colors: min->green, max->red, others->orange
                plan_summary = []
                min_c = min(numeric) if numeric else 0
                max_c = max(numeric) if numeric else 0
                for i, m in enumerate(gen_matieres):
                    coef = numeric[i]
                    allocated = alloc[i] if i < len(alloc) else 0
                    if max_c != min_c:
                        if coef == max_c:
                            color = '#ef4444'
                        elif coef == min_c:
                            color = '#16a34a'
                        else:
                            color = '#f97316'
                    else:
                        color = '#34d399'  # all same -> green-ish
                    plan_summary.append({"nom": m.get('nom'), "coefficient": coef, "allocated_hours": allocated, "color": color})

                return {"week_days": week_days, "hours": hours, "slots": slots, "summary": plan_summary}

            try:
                plan = _local_generate(gen_matieres, unavailable or {}, total_hours)
            except Exception as e2:
                plan = {"error": str(e2)}
        if isinstance(plan, dict) and not plan.get('error'):
            week_days = plan.get('week_days', [])
            slots_map = plan.get('slots', {})
            plan_summary = plan.get('summary', [])
            for d in week_days:
                day_slots = slots_map.get(d, [])
                # enrich each slot with resolved matiere dict from summary
                enriched = []
                for s in day_slots:
                    mi = s.get('matiere_idx')
                    mat = None
                    try:
                        mat = plan_summary[int(mi)] if mi is not None and int(mi) < len(plan_summary) else None
                    except Exception:
                        mat = None
                    # preserve unavailable flag from generator slots (if present)
                    enriched.append({"hour": s.get('hour'), "matiere": mat, "unavailable": bool(s.get('unavailable', False))})
                enriched_plan_days.append((d, enriched))
        # Build a full hourly calendar (8..20) and mark unavailable hours
        hours = list(range(8, 21))
        calendar_days = []
        # transform slots_map into per-day dict for quick lookup and build entries
        for d, enriched in enriched_plan_days:
            # map hour -> slot
            by_hour = {s.get('hour'): s for s in enriched if s.get('hour') is not None}
            entries = []
            u_hours = []
            try:
                if isinstance(unavailable, dict):
                    # keys may be strings; ensure day key exists
                    u_hours = unavailable.get(d) or []
            except Exception:
                u_hours = []

            for h in hours:
                # user-marked unavailable hours take absolute precedence
                if h in u_hours:
                    entries.append({"hour": h, "matiere": None, "unavailable": True})
                    continue
                if h in by_hour:
                    # if the enriched slot marked unavailable, keep that flag
                    slot = by_hour[h]
                    if slot.get('unavailable'):
                        entries.append({"hour": h, "matiere": None, "unavailable": True})
                    else:
                        entries.append({"hour": h, "matiere": slot.get('matiere'), "unavailable": False})
                else:
                    entries.append({"hour": h, "matiere": None, "unavailable": False})

            calendar_days.append((d, entries))

        # compute colors for matieres based on coefficient (green=min -> red=max)
        matiere_colors = {}
        try:
            coeffs = [float(m.get('coefficient') or m.get('coef') or 1.0) for m in plan_summary if isinstance(m, dict)]
        except Exception:
            coeffs = []
        if coeffs:
            c_min = min(coeffs)
            c_max = max(coeffs)
            span = c_max - c_min if c_max != c_min else 1.0
            for idx, m in enumerate(plan_summary):
                try:
                    coef = float(m.get('coefficient') or m.get('coef') or 1.0)
                except Exception:
                    coef = 1.0
                norm = (coef - c_min) / span
                hue = int(120 - (120 * norm))
                color = f"hsl({hue},70%,45%)"
                bg = f"hsla({hue},70%,85%,0.9)"
                name = m.get('nom') or str(idx)
                matiere_colors[name] = {"color": color, "bg": bg}
                matiere_colors[str(idx)] = {"color": color, "bg": bg}

        # attach colors to calendar entries for easy template rendering
        try:
            for di, (d, entries) in enumerate(calendar_days):
                for ei, e in enumerate(entries):
                    mat = e.get('matiere')
                    e['color'] = None
                    e['bg'] = None
                    if mat and isinstance(mat, dict):
                        name = mat.get('nom') or ''
                        col = matiere_colors.get(name)
                        if not col:
                            # try to find by identity or matching name
                            idx = None
                            try:
                                idx = next((i for i, mm in enumerate(plan_summary) if mm is mat or (isinstance(mm, dict) and mm.get('nom') == name)), None)
                            except Exception:
                                idx = None
                            if idx is not None:
                                col = matiere_colors.get(str(idx))
                        if col:
                            e['color'] = col.get('color')
                            e['bg'] = col.get('bg')
        except Exception:
            pass

        # Build a matrix of rows for easier template rendering: each row = (hour, [cell_for_day...])
        day_labels = [d for d, _ in calendar_days]
        calendar_rows = []
        for h in hours:
            row_cells = []
            for d, entries in calendar_days:
                # find matching entry for this hour
                found = None
                for e in entries:
                    try:
                        if e.get('hour') == h:
                            found = e
                            break
                    except Exception:
                        pass
                if not found:
                    found = {"hour": h, "matiere": None, "unavailable": False, "color": None, "bg": None}
                row_cells.append(found)
            calendar_rows.append((h, row_cells))
        return render(request, "program/_plan_calendar.html", {"plan": plan, "day_labels": day_labels, "calendar_rows": calendar_rows, "hours": hours, "niveau": n, "unavailable": unavailable})
    except Exception as e:
        import traceback as _tb
        tb = _tb.format_exc()
        return render(request, "program/_plan_error.html", {"error": str(e), "trace": tb})


def public_analyze_average(request: HttpRequest, niveau_id=None):
    """Analyze averages for a niveau or for a provided list of matieres.

    Accepts POST JSON payload with optional keys:
      - matieres: [{"nom":"...","coefficient":x,"grade":y}, ...]
    If no payload is provided, the endpoint will load matieres for the `niveau_id`
    and expect optional form-encoded fields `grades[<matiere_id>]`.

    Returns an HTML partial rendering the analysis.
    """
    try:
        payload = {}
        if request.method == 'POST':
            try:
                payload = json.loads(request.body.decode('utf-8')) if request.body else {}
            except Exception:
                payload = {k: request.POST.get(k) for k in request.POST}

        matieres = payload.get('matieres')
        # If matieres provided in payload, try to enrich them with DB data when
        # only an id is supplied (so per-matiere analyze button can send {id}).
        if matieres:
            enriched = []
            for m in matieres:
                # accept either {'id':...} or {'matiere_id':...}
                mid = m.get('id') or m.get('matiere_id') or m.get('_id')
                if (not m.get('nom') or not m.get('coefficient')) and mid:
                    try:
                        dbm = services.get_matiere(mid)
                        if dbm:
                            mm = {"nom": dbm.get('nom'), "coefficient": dbm.get('coefficient'), "grade": m.get('grade')}
                        else:
                            mm = {"nom": m.get('nom'), "coefficient": m.get('coefficient'), "grade": m.get('grade')}
                    except Exception:
                        mm = {"nom": m.get('nom'), "coefficient": m.get('coefficient'), "grade": m.get('grade')}
                else:
                    mm = {"nom": m.get('nom'), "coefficient": m.get('coefficient'), "grade": m.get('grade')}
                enriched.append(mm)
            matieres = enriched
        if not matieres:
            # load matieres for the niveau
            try:
                matieres = services.list_matieres(niveau_id=niveau_id, limit=200)
            except Exception:
                matieres = services.list_matieres(limit=200)
            # attach grades if provided via form mapping: grades[<matiere_id>]=value
            grades_map = {}
            # accept form-encoded grades like grades[<id>]=12 or JSON mapping
            if isinstance(payload, dict) and payload.get('grades') and isinstance(payload.get('grades'), dict):
                grades_map = payload.get('grades')
            else:
                for k, v in (request.POST.items() if request.method == 'POST' else []):
                    if k.startswith('grades[') and k.endswith(']'):
                        mid = k[len('grades['):-1]
                        try:
                            grades_map[mid] = float(v)
                        except Exception:
                            pass
            # build canonical matieres list
            canonical = []
            for m in matieres:
                mm = {"nom": m.get('nom'), "coefficient": m.get('coefficient')}
                gid = m.get('id') or str(m.get('_id') or '')
                if gid and str(gid) in grades_map:
                    try:
                        mm['grade'] = float(grades_map[str(gid)])
                    except Exception:
                        mm['grade'] = None
                else:
                    mm['grade'] = None
                canonical.append(mm)
            matieres = canonical

        # run analyzer
        res = average_analyzer.analyze(matieres, targets=[10.0, 13.0])
        return render(request, "program/_average_analysis.html", {"analysis": res, "matieres": matieres})
    except Exception as e:
        import traceback as _tb
        return render(request, "program/_plan_error.html", {"error": str(e), "trace": _tb.format_exc()})


def public_generate_plan_pre(request: HttpRequest, niveau_id=None):
    """Return an availability labeling form (HTML partial) so the user can
    mark times they are NOT available before generating the study plan.

    This endpoint is intended for HTMX. It returns a small form which will
    POST to the real `public_generate_plan` endpoint with a hidden
    `unavailable` JSON payload containing a mapping of day -> [hours].
    """
    n = services.get_niveau(niveau_id)
    if not n:
        raise Http404("Niveau not found")

    # ensure the niveau dict exposes a string id for URL reversing in templates
    try:
        if not n.get('id'):
            n['id'] = str(n.get('_id') or niveau_id)
        else:
            n['id'] = str(n.get('id'))
    except Exception:
        n['id'] = str(niveau_id or '')

    # days and hours presented to the user; generator expects keys like 'Mon','Tue',... but
    # keep labels simple (English 3-letter keys) for the payload. Adjust as needed.
    days = [
        ("Mon", "Lundi"),
        ("Tue", "Mardi"),
        ("Wed", "Mercredi"),
        ("Thu", "Jeudi"),
        ("Fri", "Vendredi"),
        ("Sat", "Samedi"),
        ("Sun", "Dimanche"),
    ]
    # Show typical study hours (8..20)
    hours = list(range(8, 21))
    return render(request, "program/_plan_availability_form.html", {"niveau": n, "days": days, "hours": hours})


def cour_view_test_inline(request: HttpRequest, cid=None):
    """Return generated questions rendered for inline replacement (HTMX)."""
    c = services.get_cour(cid)
    if not c:
        raise Http404("Cours not found")
    questions = c.get('generated_tests') or []
    # ensure cid for template links
    try:
        questions_json = json.dumps(questions)
    except Exception:
        questions_json = '[]'
    return render(request, "program/_cours_tests_inline.html", {"questions": questions, "questions_json": questions_json, "error": None, "cid": cid})


def cour_view_summary_inline(request: HttpRequest, cid=None):
    c = services.get_cour(cid)
    if not c:
        raise Http404("Cours not found")
    summary = c.get('generated_summary') or None
    return render(request, "program/_cours_summary_inline.html", {"summary": summary, "error": None, "cid": cid})


def cour_pdf_partial(request: HttpRequest, cid=None):
    c = services.get_cour(cid)
    if not c:
        raise Http404("Cours not found")
    # ensure id present for partial includes
    if not c.get('id'):
        try:
            c['id'] = str(c.get('_id') or cid)
        except Exception:
            c['id'] = str(cid or '')
    return render(request, "program/_cours_pdf_partial.html", {"cour": c})
