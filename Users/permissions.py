from rest_framework.permissions import BasePermission
from .models import RolePermission

class HasResourcePermission(BasePermission):

    def has_permission(self, request, view):

        if not request.user or not request.user.is_authenticated:
            return False

        if getattr(request.user, "is_staff", False):
            return True

        role = getattr(request.user, "role", None)
        if not role:
            return False

        resource = getattr(view, "resource", None)
        if not resource:
            return False

        if request.method == "GET":
            action = "can_read"
        elif request.method in ["POST", "PUT", "PATCH"]:
            action = "can_write"
        elif request.method == "DELETE":
            action = "can_delete"
        else:
            return False

        try:
            perm = RolePermission.objects.get(
                role=role,
                resource=resource   # ✅ FIXED
            )
            return getattr(perm, action, False)

        except RolePermission.DoesNotExist:
            return False
        
class IsAdminUserRole(BasePermission):
    """
    Allows access only to authenticated users who have the admin role or staff flag.
    """
    def has_permission(self, request, view):
        return bool(
            request.user 
            and request.user.is_authenticated 
            and (getattr(request.user, 'role', None) == 'admin' or request.user.is_staff or request.user.is_superuser)
        )

