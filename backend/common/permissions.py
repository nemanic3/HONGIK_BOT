from rest_framework.permissions import BasePermission


class IsRequestedUser(BasePermission):
    """Prevent IDOR on legacy routes without breaking their paths."""
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and view.kwargs.get('user_id') == request.user.pk)
