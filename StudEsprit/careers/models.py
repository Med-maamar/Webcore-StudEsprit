from __future__ import annotations

from typing import Any, Dict, List

import mongoengine as me
from django.core.exceptions import ValidationError
from django.utils import timezone


STATUS_CHOICES = ("draft", "submitted", "interview", "offered", "rejected")


def _normalize_list(values: List[str]) -> List[str]:
    cleaned: List[str] = []
    for value in values or []:
        if not value:
            continue
        cleaned.append(value.strip())
    seen = {}
    for item in cleaned:
        key = item.lower()
        if key not in seen:
            seen[key] = item
    return list(seen.values())


class Opportunity(me.Document):
    company = me.StringField(required=True, max_length=255)
    role = me.StringField(required=True, max_length=255)
    location = me.StringField(default="", max_length=255)
    skills = me.ListField(me.StringField(max_length=120), default=list)
    apply_url = me.URLField(required=True)
    deadline = me.DateTimeField(required=True)
    description = me.StringField()
    created_at = me.DateTimeField(default=timezone.now)
    updated_at = me.DateTimeField(default=timezone.now)
    is_active = me.BooleanField(default=True)

    meta = {
        "collection": "careers_opportunities",
        "indexes": [
            "deadline",
            "is_active",
            "created_at",
            {"fields": ["company", "role"], "name": "company_role_idx"},
            {"fields": ["skills"], "name": "skills_idx"},
        ],
        "ordering": ["-created_at"],
    }

    def clean(self):  # type: ignore[override]
        now = timezone.now()
        if self.deadline and self.deadline <= now:
            raise ValidationError("Deadline must be in the future.")
        self.skills = _normalize_list(self.skills)
        if self.description:
            self.description = self.description.strip()

    def save(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        self.updated_at = timezone.now()
        if not self.created_at:
            self.created_at = self.updated_at
        self.validate(clean=True)
        return super().save(*args, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "company": self.company,
            "role": self.role,
            "location": self.location,
            "skills": self.skills,
            "applyUrl": self.apply_url,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "description": self.description,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "isActive": self.is_active,
        }


class Application(me.Document):
    user_id = me.StringField(required=True)
    opportunity = me.ReferenceField(Opportunity, required=True, reverse_delete_rule=me.CASCADE)
    status = me.StringField(required=True, default="draft", choices=STATUS_CHOICES)
    # Accept relative paths or external URLs without strict validation
    cv_url = me.StringField()
    cover_url = me.StringField()
    cover_text = me.StringField()
    interview_prep = me.DictField()
    notes = me.StringField()
    created_at = me.DateTimeField(default=timezone.now)
    updated_at = me.DateTimeField(default=timezone.now)

    meta = {
        "collection": "careers_applications",
        "indexes": [
            "user_id",
            "status",
            "created_at",
            {"fields": ["user_id", "opportunity"], "unique": True, "name": "uniq_user_opportunity"},
        ],
        "ordering": ["-created_at"],
    }

    def clean(self):  # type: ignore[override]
        if self.status not in STATUS_CHOICES:
            raise ValidationError({"status": f"Invalid status '{self.status}'."})
        if not self.user_id:
            raise ValidationError({"user_id": "User ID is required."})

    def save(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        self.updated_at = timezone.now()
        if not self.created_at:
            self.created_at = self.updated_at
        self.validate(clean=True)
        return super().save(*args, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "userId": self.user_id,
            "opportunityId": str(self.opportunity.id) if self.opportunity else None,
            "status": self.status,
            "cvUrl": self.cv_url,
            "coverUrl": self.cover_url,
            "coverText": self.cover_text,
            "interviewPrep": self.interview_prep,
            "notes": self.notes,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Project(me.EmbeddedDocument):
    title = me.StringField(required=True, max_length=255)
    description = me.StringField()
    link = me.URLField()
    tech = me.ListField(me.StringField(max_length=120), default=list)


class ProfileLink(me.EmbeddedDocument):
    label = me.StringField(required=True, max_length=120)
    url = me.URLField(required=True)


class CVProfile(me.Document):
    user_id = me.StringField(required=True, unique=True)
    cv_url = me.StringField()
    # Saved cover letters for reuse
    # Stored as lightweight EmbeddedDocument would be ideal; using separate doc instead (see CoverLetter)
    projects = me.ListField(me.EmbeddedDocumentField(Project), default=list)
    skills = me.ListField(me.StringField(max_length=120), default=list)
    languages = me.ListField(me.StringField(max_length=120), default=list)
    links = me.ListField(me.EmbeddedDocumentField(ProfileLink), default=list)
    last_updated = me.DateTimeField(default=timezone.now)

    meta = {
        "collection": "careers_cv_profiles",
        "indexes": [
            {"fields": ["user_id"], "unique": True},
        ],
    }

    def clean(self):  # type: ignore[override]
        if not self.user_id:
            raise ValidationError({"user_id": "User ID is required."})
        self.skills = _normalize_list(self.skills)
        self.languages = _normalize_list(self.languages)
        for project in self.projects or []:
            project.tech = _normalize_list(project.tech)

    def save(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        self.last_updated = timezone.now()
        self.validate(clean=True)
        return super().save(*args, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "userId": self.user_id,
            "cvUrl": getattr(self, 'cv_url', None),
            "projects": [
                {
                    "title": project.title,
                    "description": project.description,
                    "link": project.link,
                    "tech": project.tech,
                }
                for project in self.projects or []
            ],
            "skills": self.skills,
            "languages": self.languages,
            "links": [
                {"label": link.label, "url": link.url}
                for link in self.links or []
            ],
            "lastUpdated": self.last_updated.isoformat() if self.last_updated else None,
        }


class CoverLetter(me.Document):
    user_id = me.StringField(required=True)
    title = me.StringField(required=True, max_length=255)
    content = me.StringField()
    created_at = me.DateTimeField(default=timezone.now)

    meta = {
        "collection": "careers_cover_letters",
        "indexes": ["user_id", "created_at"],
        "ordering": ["-created_at"],
    }
