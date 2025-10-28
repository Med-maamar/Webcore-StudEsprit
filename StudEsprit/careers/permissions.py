from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission


def _is_staff(user) -> bool:
    """Project uses only two roles: Admin and Student.

    Treat Admin as staff; everyone else is non-staff.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", "")
    return isinstance(role, str) and role.lower() == "admin"


class IsStaffOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return getattr(request.user, "is_authenticated", False)
        return _is_staff(request.user)


class IsOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        if _is_staff(request.user):
            return True
        user_id = getattr(request.user, "id", None)
        target_user_id = getattr(obj, "user_id", None)
        if target_user_id is None and hasattr(obj, "user"):
            target_user_id = getattr(obj.user, "id", None)
        return user_id is not None and str(user_id) == str(target_user_id)

    def has_permission(self, request, view):
        return getattr(request.user, "is_authenticated", False)
