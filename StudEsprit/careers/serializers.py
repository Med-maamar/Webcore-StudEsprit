from __future__ import annotations

from typing import Any

from django.utils import timezone
from rest_framework import serializers
from rest_framework_mongoengine import serializers as me_serializers

from .models import (
    Application,
    CVProfile,
    Opportunity,
    ProfileLink,
    Project,
    STATUS_CHOICES,
)


class OpportunitySerializer(me_serializers.DocumentSerializer):
    id = serializers.CharField(read_only=True, source="pk")
    skills = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = Opportunity
        fields = (
            "id",
            "company",
            "role",
            "location",
            "skills",
            "apply_url",
            "deadline",
            "description",
            "created_at",
            "updated_at",
            "is_active",
        )
        read_only_fields = ("created_at", "updated_at")

    def validate_deadline(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Deadline must be in the future.")
        return value

    def validate_skills(self, value):
        return [skill.strip() for skill in value if skill.strip()]


class ProjectSerializer(me_serializers.EmbeddedDocumentSerializer):
    tech = serializers.ListField(child=serializers.CharField(), required=False)
    # Make optional fields lenient: accept blank strings
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    link = serializers.URLField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Project
        fields = ("title", "description", "link", "tech")

    def validate_tech(self, value):
        return [item.strip() for item in value if item.strip()]


class ProfileLinkSerializer(me_serializers.EmbeddedDocumentSerializer):
    class Meta:
        model = ProfileLink
        fields = ("label", "url")


class ApplicationSerializer(me_serializers.DocumentSerializer):
    id = serializers.CharField(read_only=True, source="pk")
    user_id = serializers.CharField(read_only=True)
    opportunity = serializers.CharField()
    cv_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cover_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cover_text = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Application
        fields = (
            "id",
            "user_id",
            "opportunity",
            "status",
            "cv_url",
            "cover_url",
            "cover_text",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def validate_status(self, value: str) -> str:
        if value not in STATUS_CHOICES:
            raise serializers.ValidationError("Invalid application status.")
        return value

    # Defer opportunity resolution to create(); keep raw id here to avoid coercion issues.

    def create(self, validated_data: dict[str, Any]) -> Application:
        request = self.context.get("request")
        if not request or not getattr(request, "user", None):
            raise serializers.ValidationError("Authenticated user required.")
        opp_id = validated_data.pop("opportunity", None)
        opp = None
        if opp_id:
            opp = Opportunity.objects(pk=str(opp_id)).first()
        if not opp:
            raise serializers.ValidationError({"opportunity": "Opportunity not found."})
        validated_data["opportunity"] = opp
        validated_data["user_id"] = str(request.user.id)
        # Prevent duplicate applications for the same user/opportunity
        from .models import Application as AppModel
        if AppModel.objects(user_id=validated_data["user_id"], opportunity=opp).first():
            raise serializers.ValidationError({
                "non_field_errors": ["Vous avez déjà postulé à cette opportunité."],
            })
        return super().create(validated_data)

    def update(self, instance: Application, validated_data: dict[str, Any]) -> Application:
        validated_data.pop("user_id", None)
        return super().update(instance, validated_data)


class CVProfileSerializer(me_serializers.DocumentSerializer):
    projects = ProjectSerializer(many=True, required=False)
    links = ProfileLinkSerializer(many=True, required=False)
    skills = serializers.ListField(child=serializers.CharField(), required=False)
    languages = serializers.ListField(child=serializers.CharField(), required=False)
    user_id = serializers.CharField(read_only=True)

    class Meta:
        model = CVProfile
        fields = (
            "user_id",
            "projects",
            "skills",
            "languages",
            "links",
            "last_updated",
        )
        read_only_fields = ("last_updated",)

    def update(self, instance: CVProfile, validated_data: dict[str, Any]) -> CVProfile:
        projects = validated_data.pop("projects", None)
        links = validated_data.pop("links", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if projects is not None:
            cleaned_projects = []
            for project in projects:
                p = dict(project)
                # Drop empty link to avoid URL validation on blank strings
                if not p.get("link"):
                    p.pop("link", None)
                # Normalize optional description
                if p.get("description") is None:
                    p["description"] = ""
                cleaned_projects.append(Project(**p))
            instance.projects = cleaned_projects
        if links is not None:
            instance.links = [ProfileLink(**link) for link in links]
        instance.save()
        return instance

    def validate_skills(self, value):
        return [item.strip() for item in value if item.strip()]

    def validate_languages(self, value):
        return [item.strip() for item in value if item.strip()]
