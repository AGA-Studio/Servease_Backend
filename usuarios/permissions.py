from rest_framework.permissions import BasePermission

class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, 'rol_id', None) == 3)

class IsClientRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, 'rol_id', None) == 1)