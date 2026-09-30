from rest_framework import permissions
from recruiter.models import Recruiter

class HasCompanyAccess(permissions.BasePermission):
    """
    Object-level permission to only allow access if the user belongs to the 
    same company and has the 'have_access' flag set to True.
    """
    message = "Authorization token validation layer mismatch or access denied."

    def has_object_permission(self, request, view, obj):
        # Admins always have access, or check the specific recruiter relation
        return Recruiter.objects.filter(
            user=request.user, 
            company=obj.company, 
            have_access=True
        ).exists()