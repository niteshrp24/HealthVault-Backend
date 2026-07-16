from rest_framework.permissions import BasePermission


class IsAdminPortal(BasePermission):
    """Allows access only to tokens with portal=admin claim."""
    message = 'Admin portal access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'portal', None) == 'admin'
        )


class IsLabPortal(BasePermission):
    """Allows access only to tokens with portal=lab claim."""
    message = 'Lab/Hospital portal access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'portal', None) == 'lab'
        )


class IsUserPortal(BasePermission):
    """Allows access only to tokens with portal=user claim."""
    message = 'User portal access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'portal', None) == 'user'
        )


class IsLabOrAdmin(BasePermission):
    """Allows lab or admin portal access."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'portal', None) in ('lab', 'admin')
        )
