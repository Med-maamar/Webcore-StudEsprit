from __future__ import annotations

import datetime
import re
from typing import Dict, List, Optional

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView
from mongoengine.queryset.visitor import Q
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_mongoengine import viewsets as me_viewsets

from .models import Application, CVProfile, Opportunity
from .permissions import IsOwnerOrStaff, IsStaffOrReadOnly, _is_staff
from .serializers import ApplicationSerializer, CVProfileSerializer, OpportunitySerializer
from .services.ai_career import CareerAIService
from .models import CoverLetter


class CareersPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    value = value.lower()
    if value in {"true", "1", "yes", "on"}:
        return True
    if value in {"false", "0", "no", "off"}:
        return False
    return None


def _split_to_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_projects(raw: Optional[str]) -> List[Dict[str, str]]:
    projects: List[Dict[str, str]] = []
    if not raw:
        return projects
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|")]
        title = parts[0] if parts else ""
        if not title:
            continue
        description = parts[1] if len(parts) > 1 else ""
        link = parts[2] if len(parts) > 2 else ""
        tech = _split_to_list(parts[3] if len(parts) > 3 else "")
        projects.append({
            "title": title,
            "description": description,
            "link": link,
            "tech": tech,
        })
    return projects


def _parse_links(raw: Optional[str]) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    if not raw:
        return links
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 2:
            links.append({"label": parts[0], "url": parts[1]})
    return links


def _profile_form_values(profile: CVProfile) -> Dict[str, str]:
    projects_lines = []
    for project in profile.projects:
        tech = ",".join(project.tech)
        projects_lines.append(" | ".join(filter(None, [project.title, project.description, project.link, tech])))
    links_lines = []
    for link in profile.links:
        links_lines.append(f"{link.label} | {link.url}")
    return {
        "skills": ", ".join(profile.skills),
        "languages": ", ".join(profile.languages),
        "projects": "\n".join(projects_lines),
        "links": "\n".join(links_lines),
    }


def _build_opportunity_queryset(request: HttpRequest):
    qs = Opportunity.objects
    if not _is_staff(request.user):
        qs = qs.filter(is_active=True)

    params = request.query_params if hasattr(request, "query_params") else request.GET

    location = params.get("location")
    if location:
        qs = qs.filter(location__icontains=location)

    skills_param = params.get("skills")
    if skills_param:
        skills = [skill.strip() for skill in skills_param.split(",") if skill.strip()]
        if skills:
            regexes = [re.compile(f"^{re.escape(skill)}$", re.IGNORECASE) for skill in skills]
            qs = qs.filter(__raw__={"skills": {"$all": regexes}})

    before_param = params.get("before")
    if before_param:
        try:
            deadline = datetime.datetime.fromisoformat(before_param)
            if deadline.tzinfo is None:
                deadline = timezone.make_aware(deadline, timezone=timezone.get_current_timezone())
            qs = qs.filter(deadline__lte=deadline)
        except ValueError:
            pass

    active_param = _parse_bool(params.get("active"))
    if active_param is not None:
        qs = qs.filter(is_active=active_param)

    search = params.get("search") or params.get("q")
    if search:
        query = (
            Q(company__icontains=search)
            | Q(role__icontains=search)
            | Q(description__icontains=search)
        )
        qs = qs.filter(query)

    return qs.order_by("-created_at")


class OpportunityViewSet(me_viewsets.ModelViewSet):
    serializer_class = OpportunitySerializer
    permission_classes = [IsAuthenticated, IsStaffOrReadOnly]
    pagination_class = CareersPagination

    def get_queryset(self):
        return _build_opportunity_queryset(self.request)


class ApplicationViewSet(me_viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]
    pagination_class = CareersPagination

    def get_queryset(self):
        qs = Application.objects
        if _is_staff(self.request.user):
            return qs.order_by("-created_at")
        return qs.filter(user_id=str(getattr(self.request.user, "id", ""))).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save()


class CVProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CVProfileSerializer

    def _get_profile(self, request: HttpRequest) -> CVProfile:
        user_id = str(getattr(request.user, "id", ""))
        if not user_id:
            raise Http404("User not authenticated")
        profile = CVProfile.objects(user_id=user_id).first()
        if profile is None:
            profile = CVProfile(user_id=user_id)
            profile.save()
        return profile

    def list(self, request: HttpRequest):
        profile = self._get_profile(request)
        serializer = self.serializer_class(profile)
        return Response(serializer.data)

    def partial_update(self, request: HttpRequest, pk: Optional[str] = None):
        profile = self._get_profile(request)
        serializer = self.serializer_class(profile, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def update(self, request: HttpRequest, pk: Optional[str] = None):
        return self.partial_update(request, pk)


class CvGapAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: HttpRequest):
        data = request.data or {}
        job_desc = data.get("jobDesc")
        if not job_desc:
            return Response({"detail": "jobDesc is required."}, status=status.HTTP_400_BAD_REQUEST)
        service = CareerAIService.create()
        try:
            result = service.analyze_cv_gap(job_desc, data.get("cvText", ""), data.get("cvUrl", ""))
            return Response(result)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CoverLetterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: HttpRequest):
        data = request.data or {}
        job_desc = data.get("jobDesc")
        if not job_desc:
            return Response({"detail": "jobDesc is required."}, status=status.HTTP_400_BAD_REQUEST)
        tone = data.get("tone", "professional")
        achievements = data.get("achievements", [])
        service = CareerAIService.create()
        try:
            result = service.generate_cover_letter(job_desc, data.get("cvText", ""), achievements, tone)
            return Response(result)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InterviewPrepView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: HttpRequest):
        data = request.data or {}
        job_desc = data.get("jobDesc")
        if not job_desc:
            return Response({"detail": "jobDesc is required."}, status=status.HTTP_400_BAD_REQUEST)
        service = CareerAIService.create()
        try:
            result = service.generate_interview_prep(job_desc, data.get("skills", []), data.get("level", "junior"))
            return Response(result)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# -----------------------
# Frontend HTMX views
# -----------------------


class OpportunityListPageView(LoginRequiredMixin, TemplateView):
    template_name = "careers/opportunity_list.html"

    def get_context_data(self, **kwargs: Dict[str, str]):
        context = super().get_context_data(**kwargs)
        queryset = _build_opportunity_queryset(self.request)
        context["opportunities"] = queryset[:50]
        context["filters"] = {
            "location": self.request.GET.get("location", ""),
            "skills": self.request.GET.get("skills", ""),
            "search": self.request.GET.get("search", ""),
        }
        return context

    def render_to_response(self, context, **response_kwargs):
        template = (
            "careers/partials/opportunity_items.html"
            if self.request.headers.get("HX-Request") == "true"
            else self.template_name
        )
        return render(self.request, template, context, **response_kwargs)


class OpportunityCreateView(LoginRequiredMixin, View):
    template_name = "careers/partials/opportunity_create_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not _is_staff(request.user):
            raise Http404("Not found")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name, {"errors": {}, "initial": {"is_active": True}})

    def post(self, request: HttpRequest) -> HttpResponse:
        payload = {
            "company": request.POST.get("company", "").strip(),
            "role": request.POST.get("role", "").strip(),
            "location": request.POST.get("location", "").strip(),
            "skills": _split_to_list(request.POST.get("skills")),
            "apply_url": request.POST.get("apply_url", "").strip(),
            "deadline": request.POST.get("deadline"),
            "description": request.POST.get("description", "").strip(),
            "is_active": request.POST.get("is_active") == "on",
        }
        serializer = OpportunitySerializer(data=payload)
        if serializer.is_valid():
            serializer.save()
            context = {"created": True}
            return render(request, "careers/partials/opportunity_create_success.html", context, status=201)
        return render(request, self.template_name, {"errors": serializer.errors, "initial": payload}, status=400)


class OpportunityEditView(LoginRequiredMixin, View):
    template_name = "careers/partials/opportunity_update_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not _is_staff(request.user):
            raise Http404("Not found")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, pk: str) -> Opportunity:
        obj = Opportunity.objects(pk=pk).first()
        if not obj:
            raise Http404("Opportunity not found")
        return obj

    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        opp = self.get_object(pk)
        initial = {
            "company": opp.company,
            "role": opp.role,
            "location": opp.location,
            "skills": ", ".join(opp.skills or []),
            "apply_url": opp.apply_url,
            "deadline": opp.deadline.strftime("%Y-%m-%dT%H:%M") if opp.deadline else "",
            "description": opp.description,
            "is_active": opp.is_active,
        }
        return render(request, self.template_name, {"errors": {}, "initial": initial, "pk": str(opp.id)})

    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        opp = self.get_object(pk)
        payload = {
            "company": request.POST.get("company", "").strip(),
            "role": request.POST.get("role", "").strip(),
            "location": request.POST.get("location", "").strip(),
            "skills": _split_to_list(request.POST.get("skills")),
            "apply_url": request.POST.get("apply_url", "").strip(),
            "deadline": request.POST.get("deadline"),
            "description": request.POST.get("description", "").strip(),
            "is_active": request.POST.get("is_active") == "on",
        }
        serializer = OpportunitySerializer(opp, data=payload, partial=True)
        if serializer.is_valid():
            serializer.save()
            return render(request, "careers/partials/opportunity_create_success.html", {"created": True}, status=200)
        return render(request, self.template_name, {"errors": serializer.errors, "initial": payload, "pk": str(opp.id)}, status=400)


class OpportunityDeleteView(LoginRequiredMixin, View):
    template_name = "careers/partials/opportunity_delete_confirm.html"

    def dispatch(self, request, *args, **kwargs):
        if not _is_staff(request.user):
            raise Http404("Not found")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        return render(request, self.template_name, {"pk": pk})

    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        opp = Opportunity.objects(pk=pk).first()
        if opp:
            opp.delete()
        return render(request, "careers/partials/opportunity_delete_success.html", {}, status=200)


class OpportunityDetailPageView(LoginRequiredMixin, DetailView):
    template_name = "careers/opportunity_detail.html"
    context_object_name = "opportunity"

    def get_object(self, queryset=None):
        pk = self.kwargs.get("pk")
        opportunity = Opportunity.objects(pk=pk).first()
        if not opportunity:
            raise Http404("Opportunity not found")
        if not opportunity.is_active and not _is_staff(self.request.user):
            raise Http404("Opportunity not available")
        return opportunity


class OpportunityApplyView(LoginRequiredMixin, View):
    template_name = "careers/partials/application_form.html"

    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        opportunity = self._get_opportunity(pk)
        # Only students can apply (not admins)
        from .permissions import _is_staff
        if _is_staff(request.user):
            raise Http404("Admins cannot apply to opportunities")
        # If already applied, show success summary instead of form
        existing = Application.objects(user_id=str(request.user.id), opportunity=opportunity).first()
        if existing:
            return render(
                request,
                "careers/partials/application_success.html",
                {"opportunity": opportunity, "application": existing},
                status=200,
            )
        serializer = ApplicationSerializer()
        # Fetch saved CV and cover letters for this user
        profile = CVProfile.objects(user_id=str(request.user.id)).first()
        saved_covers = list(CoverLetter.objects(user_id=str(request.user.id)).order_by('-created_at')[:20])
        context = {
            "opportunity": opportunity,
            "serializer": serializer,
            "initial": {"status": "submitted"},
            "errors": {},
            "cv_url": getattr(profile, 'cv_url', None) if profile else None,
            "saved_covers": saved_covers,
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        opportunity = self._get_opportunity(pk)
        from .permissions import _is_staff
        if _is_staff(request.user):
            raise Http404("Admins cannot apply to opportunities")
        data = {
            "opportunity": str(opportunity.id),
            "status": request.POST.get("status", "submitted"),
            "cv_url": request.POST.get("cv_url"),
            "cover_url": request.POST.get("cover_url"),
            "cover_text": request.POST.get("cover_text"),
            "notes": request.POST.get("notes"),
        }
        serializer = ApplicationSerializer(data=data, context={"request": request})
        template = "careers/partials/application_success.html"
        if serializer.is_valid():
            try:
                serializer.save()
            except Exception as e:
                # Handle duplicate index race or NotUniqueError gracefully
                from mongoengine.errors import NotUniqueError
                from pymongo.errors import DuplicateKeyError
                if isinstance(e, (NotUniqueError, DuplicateKeyError)):
                    existing = Application.objects(user_id=str(request.user.id), opportunity=opportunity).first()
                    if existing:
                        return render(request, template, {"opportunity": opportunity, "application": existing}, status=200)
                # Unexpected error: re-raise
                raise
            context = {"opportunity": opportunity, "application": serializer.instance}
            return render(request, template, context, status=201)
        context = {
            "opportunity": opportunity,
            "serializer": serializer,
            "initial": serializer.initial_data,
            "errors": serializer.errors,
        }
        # Return 200 with inline errors to avoid Bad Request overlay in HTMX
        return render(request, self.template_name, context)

    @staticmethod
    def _get_opportunity(pk: str) -> Opportunity:
        opportunity = Opportunity.objects(pk=pk).first()
        if not opportunity:
            raise Http404("Opportunity not found")
        if not opportunity.is_active:
            raise Http404("Opportunity not active")
        return opportunity


class CoverLetterHTMXView(LoginRequiredMixin, View):
    template_name = "careers/partials/cover_letter_result.html"

    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        opportunity = Opportunity.objects(pk=pk).first()
        if not opportunity:
            raise Http404("Opportunity not found")
        service = CareerAIService.create()
        job_desc = opportunity.description or f"Role: {opportunity.role} at {opportunity.company}"
        # Append user profile context to help model personalize
        profile = CVProfile.objects(user_id=str(request.user.id)).first()
        cv_text = ""
        if profile:
            cv_text = f"Skills: {', '.join(profile.skills)}. Languages: {', '.join(profile.languages)}."
        tone = request.POST.get("tone", "professional")
        result = service.generate_cover_letter(job_desc, cv_text=cv_text, achievements=[], tone=tone)
        context = {"opportunity": opportunity, "markdown": result.get("markdown", ""), "job_desc": job_desc, "tone": tone}
        return render(request, self.template_name, context)


class CoverLetterSaveView(LoginRequiredMixin, APIView):
    def post(self, request: HttpRequest):
        job_desc = (request.data or {}).get("jobDesc") or request.POST.get("jobDesc")
        tone = (request.data or {}).get("tone") or request.POST.get("tone", "professional")
        if not job_desc:
            return Response({"detail": "jobDesc is required"}, status=400)
        # If client provided content directly, save as-is
        direct_content = (request.data or {}).get("content") or request.POST.get("content")
        # Build cv_text from profile
        profile = CVProfile.objects(user_id=str(request.user.id)).first()
        cv_text = ""
        if profile:
            cv_text = f"Skills: {', '.join(profile.skills)}. Languages: {', '.join(profile.languages)}."
        if direct_content:
            text = direct_content
        else:
            service = CareerAIService.create()
            out = service.generate_cover_letter(job_desc, cv_text=cv_text, tone=tone)
            text = out.get("markdown", "")
        title = (job_desc[:60] + "...") if len(job_desc) > 60 else job_desc
        CoverLetter(user_id=str(request.user.id), title=title or "Lettre générée", content=text).save()
        # If HTMX, return a small HTML confirmation (keeps UI clean)
        if request.headers.get("HX-Request") == "true":
            html = (
                "<div class=\"p-2 rounded bg-green-50 text-green-700 border border-green-200 text-sm\">"
                "Lettre enregistrée. Vous pourrez la sélectionner lors de la candidature." 
                "</div>"
            )
            return Response(html, content_type="text/html")
        items = [
            {"id": str(c.id), "title": c.title, "created_at": c.created_at.isoformat()}
            for c in CoverLetter.objects(user_id=str(request.user.id)).order_by("-created_at")[:20]
        ]
        return Response({"markdown": text, "saved": items})


class CVProfilePageView(LoginRequiredMixin, TemplateView):
    template_name = "careers/profile.html"

    def get_context_data(self, **kwargs: Dict[str, str]):
        context = super().get_context_data(**kwargs)
        profile = CVProfile.objects(user_id=str(self.request.user.id)).first()
        if not profile:
            profile = CVProfile(user_id=str(self.request.user.id))
            profile.save()
        context["profile"] = profile
        context["form_values"] = _profile_form_values(profile)
        context["errors"] = {}
        context["success"] = False
        return context

    def post(self, request: HttpRequest):
        profile = CVProfile.objects(user_id=str(request.user.id)).first()
        if not profile:
            profile = CVProfile(user_id=str(request.user.id))
            profile.save()

        payload = {
            "skills": _split_to_list(request.POST.get("skills")),
            "languages": _split_to_list(request.POST.get("languages")),
            "projects": _parse_projects(request.POST.get("projects")),
            "links": _parse_links(request.POST.get("links")),
        }

        serializer = CVProfileSerializer(profile, data=payload, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            profile.reload()
            context = {
                "profile": profile,
                "form_values": _profile_form_values(profile),
                "errors": {},
                "success": True,
            }
            template = "careers/partials/profile_form.html" if request.headers.get("HX-Request") == "true" else self.template_name
            return render(request, template, context)
        context = {
            "profile": profile,
            "form_values": {
                "skills": request.POST.get("skills", ""),
                "languages": request.POST.get("languages", ""),
                "projects": request.POST.get("projects", ""),
                "links": request.POST.get("links", ""),
            },
            "errors": serializer.errors,
            "success": False,
        }
        template = "careers/partials/profile_form.html" if request.headers.get("HX-Request") == "true" else self.template_name
        # Always return 200 for HTMX form re-render to avoid global Bad Request overlays.
        return render(request, template, context)


class ProfileGapAnalysisView(LoginRequiredMixin, View):
    template_name = "careers/partials/cv_gap_result.html"

    def post(self, request: HttpRequest) -> HttpResponse:
        job_desc = request.POST.get("job_desc")
        if not job_desc:
            context = {"error": "Please provide a job description."}
            return render(request, self.template_name, context, status=400)
        profile = CVProfile.objects(user_id=str(request.user.id)).first()
        cv_text = ""
        if profile:
            skills = ", ".join(profile.skills)
            languages = ", ".join(profile.languages)
            cv_text = f"Skills: {skills}. Languages: {languages}."
        service = CareerAIService.create()
        result = service.analyze_cv_gap(job_desc, cv_text=cv_text)
        context = {"result": result}
        return render(request, self.template_name, context)


# Utility view mapping for profile API (singleton)
profile_api_view = CVProfileViewSet.as_view({"get": "list", "patch": "partial_update", "put": "update"})


class MyApplicationsPageView(LoginRequiredMixin, TemplateView):
    template_name = "careers/my_applications.html"

    def dispatch(self, request, *args, **kwargs):
        # Page réservée aux étudiants (non-admin)
        if _is_staff(request.user):
            raise Http404("Not found")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user_id = str(getattr(self.request.user, "id", ""))
        apps = Application.objects(user_id=user_id).order_by("-created_at")
        profile = CVProfile.objects(user_id=user_id).first()
        ctx.update({
            "applications": apps,
            "profile": profile,
        })
        return ctx


class InterviewPrepHTMLView(LoginRequiredMixin, View):
    template_name = "careers/partials/interview_prep_result.html"

    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        # Only the owner student can request prep
        app = Application.objects(pk=pk).first()
        if not app or str(app.user_id) != str(request.user.id) or _is_staff(request.user):
            raise Http404("Application not found")
        job_desc = ""
        if app.opportunity and app.opportunity.description:
            job_desc = app.opportunity.description
        elif app.opportunity:
            job_desc = f"Role: {app.opportunity.role} at {app.opportunity.company}"
        profile = CVProfile.objects(user_id=str(request.user.id)).first()
        skills = profile.skills if profile else []
        service = CareerAIService.create()
        result = service.generate_hard_interview(job_desc, skills=skills)
        # Save to application for later review
        app.interview_prep = result
        app.save()
        resp = render(request, self.template_name, {"result": result, "app_id": str(app.id)})
        # Notify page to refresh (htmx client can choose to reload)
        resp["HX-Trigger"] = "applications-refresh"
        return resp


class InterviewPrepDeleteView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        app = Application.objects(pk=pk).first()
        if not app or str(app.user_id) != str(request.user.id) or _is_staff(request.user):
            raise Http404("Application not found")
        app.interview_prep = None
        app.save()
        resp = HttpResponse("", status=204)
        resp["HX-Trigger"] = "applications-refresh"
        return resp
