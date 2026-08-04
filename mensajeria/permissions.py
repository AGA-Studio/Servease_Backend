from rest_framework.permissions import BasePermission


class IsParticipant(BasePermission):
    """
    Object-level permission: user must be the cliente or proveedor
    of the conversation. Expects obj to be a Conversacion instance
    or a view with get_conversacion() method.

    NOTE: str() normalization is required because Usuario uses
    managed=False — Django never applies UUIDField type conversion
    on reads, so user.id_usuario stays a str. Conversacion FKs
    (managed=True) return uuid.UUID from the DB. Without str(),
    the comparison always evaluates to False.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        conversacion = getattr(obj, "conversacion", obj)
        return str(conversacion.cliente_id) == str(user.id_usuario) or str(
            conversacion.proveedor_id
        ) == str(user.id_usuario)


class IsEmisor(BasePermission):
    """
    Object-level permission: only the message author can edit/delete.
    Expects obj to be a Mensaje instance.
    Safe methods (GET, HEAD, OPTIONS) are always allowed for participants.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Not a Mensaje — this permission doesn't apply; skip so others can decide
        if not hasattr(obj, "emisor_id"):
            return True
        # Any participant can read; only emisor can write
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return str(obj.emisor_id) == str(user.id_usuario)
