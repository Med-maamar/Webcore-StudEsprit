from __future__ import annotations

from django.shortcuts import render, redirect
from core.decorators import login_required_mongo


def coming_soon(request):
    return render(request, "stubs/coming_soon.html")


def home(request):
    user = getattr(request, "user", None)
    # Only admins go to the dashboard; students stay on the public site
    if user and user.is_authenticated and getattr(user, "role", "Student") == "Admin":
        return redirect("/dashboard/")

    roles = [
        {
            "title": "Students",
            "subtitle": "Learn & grow",
            "body": "Track courses, get AI-assisted study plans, explore recommended events, and manage your learning journey in one place.",
            "accent": "bg-emerald-500/10 text-emerald-400",
            "badge": "Accessible learning",
        },
        {
            "title": "Moderators",
            "subtitle": "Guide the community",
            "body": "Curate discussions, review submissions, and keep the campus vibrant with streamlined moderation panels.",
            "accent": "bg-sky-500/10 text-sky-400",
            "badge": "Community first",
        },
        {
            "title": "Admins",
            "subtitle": "Orchestrate operations",
            "body": "Oversee users, monitor analytics, and personalize experiences powered by MongoDB Atlas Vector Search.",
            "accent": "bg-amber-500/10 text-amber-400",
            "badge": "Operational clarity",
        },
    ]

    highlights = [
        {
            "title": "Mongo-native accounts",
            "body": "Fast, scalable user management stored entirely in MongoDB with Argon2 security.",
        },
        {
            "title": "Personalized dashboards",
            "body": "Vector-search powered recommendations tailor each experience, role by role.",
        },
        {
            "title": "Modern UI toolkit",
            "body": "Built with Tailwind, Flowbite, and HTMX for a fluid, accessible interface.",
        },
    ]

    return render(
        request,
        "public/home.html",
        {
            "roles": roles,
            "highlights": highlights,
        },
    )
