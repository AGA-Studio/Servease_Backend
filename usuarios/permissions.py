from rest_framework.permissions import BasePermission

# Espeja la jerarquia de roles del frontend (src/router/RoleRoute.tsx):
# admin hereda todo lo de proveedor, y proveedor hereda todo lo de cliente.
CLIENT_ROLE_IDS = {1, 2, 3}
PROVIDER_ROLE_IDS = {2, 3}
ADMIN_ROLE_IDS = {3}


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, 'rol_id', None) in ADMIN_ROLE_IDS)

class IsClientRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, 'rol_id', None) in CLIENT_ROLE_IDS)

class IsProviderRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, 'rol_id', None) in PROVIDER_ROLE_IDS)
