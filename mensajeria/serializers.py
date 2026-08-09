from django.db.models import Avg
from rest_framework import serializers

from calificaciones.models import Calificacion
from mensajeria.models import Conversacion, Mensaje
from servicios.models.estado import ACTIVA
from usuarios.models import Usuario


class UsuarioMinimoSerializer(serializers.ModelSerializer):
    """Minimal user info for conversation detail."""

    rating = serializers.SerializerMethodField()
    num_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = (
            "id_usuario",
            "nombre",
            "apellido_pa",
            "url_foto_perfil",
            "rating",
            "num_reviews",
        )

    def get_rating(self, obj):
        avg = Calificacion.objects.filter(evaluado_id=obj.id_usuario).aggregate(
            avg=Avg("puntuacion")
        )["avg"]
        return round(avg, 1) if avg is not None else None

    def get_num_reviews(self, obj):
        return Calificacion.objects.filter(evaluado_id=obj.id_usuario).count()


class ServicioMinimoSerializer(serializers.Serializer):
    """Minimal service info for conversation detail."""

    id = serializers.IntegerField(source="id_servicio")
    titulo = serializers.CharField()
    fecha = serializers.DateTimeField()
    categoria = serializers.CharField(source="categoria.nombre", default=None)


class ConversacionListSerializer(serializers.ModelSerializer):
    """
    Maps to frontend Chat interface:
    { id, name, avatar, professionKey, lastMessagePreview, timeAgoKey, unreadCount }
    """

    id = serializers.IntegerField(source="id_conversacion")
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    professionKey = serializers.SerializerMethodField()
    lastMessagePreview = serializers.CharField(source="ultimo_mensaje_preview")
    timeAgoKey = serializers.SerializerMethodField()
    unreadCount = serializers.SerializerMethodField()
    servicio_titulo = serializers.CharField(source="servicio.titulo", default=None, read_only=True)
    cliente_id = serializers.UUIDField(read_only=True)
    proveedor_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Conversacion
        fields = (
            "id",
            "name",
            "avatar",
            "professionKey",
            "lastMessagePreview",
            "timeAgoKey",
            "unreadCount",
            "servicio_id",
            "servicio_titulo",
            "cliente_id",
            "proveedor_id",
        )

    def _get_other_user(self, obj):
        user = self.context["request"].user
        if str(obj.cliente_id) == str(user.id_usuario):
            return obj.proveedor
        return obj.cliente

    def get_name(self, obj):
        other = self._get_other_user(obj)
        return f"{other.nombre} {other.apellido_pa}"

    def get_avatar(self, obj):
        other = self._get_other_user(obj)
        return other.url_foto_perfil or ""

    def get_professionKey(self, obj):
        other = self._get_other_user(obj)
        if other.categoria:
            return other.categoria.nombre
        return ""

    def get_unreadCount(self, obj):
        # unread_count_* es por destinatario: cada lado de la conversación
        # solo debe ver los mensajes que a ÉL le faltan por leer, no los que
        # el otro participante aún no ha leído de los suyos.
        user = self.context["request"].user
        if str(obj.cliente_id) == str(user.id_usuario):
            return obj.unread_count_cliente
        return obj.unread_count_proveedor

    def get_timeAgoKey(self, obj):
        if not obj.ultimo_mensaje_fecha:
            return ""
        from django.utils import timezone

        now = timezone.now()
        diff = now - obj.ultimo_mensaje_fecha
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"


class ConversacionDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_conversacion")
    cliente = UsuarioMinimoSerializer(read_only=True)
    proveedor = UsuarioMinimoSerializer(read_only=True)
    servicio = ServicioMinimoSerializer(read_only=True)
    cliente_id = serializers.UUIDField(read_only=True)
    proveedor_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Conversacion
        fields = (
            "id",
            "estado",
            "fecha_inicio",
            "cliente",
            "proveedor",
            "servicio",
            "cliente_id",
            "proveedor_id",
        )


class MensajeSerializer(serializers.ModelSerializer):
    """
    Maps to frontend Message interface:
    { id, sender, senderName, senderAvatar, text, time, leido, editado, estado_entrega, tipo_mensaje, archivo, reply_to }
    """

    id = serializers.IntegerField(source="id_mensaje")
    sender = serializers.SerializerMethodField()
    senderName = serializers.SerializerMethodField()
    senderAvatar = serializers.SerializerMethodField()
    text = serializers.CharField(source="contenido")
    time = serializers.SerializerMethodField()
    estado_entrega = serializers.CharField(read_only=True)
    tipo_mensaje = serializers.CharField(read_only=True)
    archivo = serializers.FileField(read_only=True)
    reply_to = serializers.SerializerMethodField()

    class Meta:
        model = Mensaje
        fields = (
            "id",
            "sender",
            "senderName",
            "senderAvatar",
            "text",
            "time",
            "leido",
            "editado",
            "estado_entrega",
            "tipo_mensaje",
            "archivo",
            "reply_to",
        )

    def get_sender(self, obj):
        user = self.context["request"].user
        return "user" if str(obj.emisor_id) == str(user.id_usuario) else "other"

    def get_senderName(self, obj):
        return f"{obj.emisor.nombre} {obj.emisor.apellido_pa}"

    def get_senderAvatar(self, obj):
        return obj.emisor.url_foto_perfil or ""

    def get_time(self, obj):
        from django.utils import timezone

        t = obj.fecha
        if timezone.is_naive(t):
            t = timezone.make_aware(t)
        local = timezone.localtime(t)
        return local.strftime("%I:%M %p").lstrip("0").lower()

    def get_reply_to(self, obj):
        if obj.reply_to:
            return obj.reply_to.id_mensaje
        return None


class CreateConversacionSerializer(serializers.Serializer):
    proveedor_id = serializers.UUIDField()
    servicio_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_proveedor_id(self, value):
        try:
            user = Usuario.objects.get(id_usuario=value)
        except Usuario.DoesNotExist:
            raise serializers.ValidationError("Proveedor no encontrado.")
        if not hasattr(user, "rol") or user.rol_id != 2:
            raise serializers.ValidationError("El usuario no es proveedor.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        proveedor_id = attrs["proveedor_id"]
        servicio_id = attrs.get("servicio_id")

        if request.user.id_usuario == proveedor_id:
            raise serializers.ValidationError(
                {"proveedor_id": "No puedes crear una conversacion contigo mismo."}
            )

        if servicio_id:
            from servicios.models import Servicio

            try:
                servicio = Servicio.objects.get(pk=servicio_id)
            except Servicio.DoesNotExist:
                raise serializers.ValidationError(
                    {"servicio_id": "Servicio no encontrado."}
                )
            if servicio.cliente_id != request.user.id_usuario:
                raise serializers.ValidationError(
                    {"servicio_id": "No eres el cliente de este servicio."}
                )
            attrs["servicio"] = servicio
        else:
            attrs["servicio"] = None

        existing = Conversacion.objects.filter(
            cliente=request.user,
            proveedor_id=proveedor_id,
            servicio=attrs["servicio"],
            estado_id=ACTIVA,
        ).first()
        if existing:
            attrs["existing"] = existing

        return attrs

_MAGIC_BYTES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
    "application/pdf": (b"%PDF-",),
}


def _matches_magic(archivo):
    """Verify file content matches its declared content_type (magic bytes)."""
    ct = archivo.content_type
    if ct == "text/plain":
        return True  # no reliable binary signature; accept text
    signatures = _MAGIC_BYTES.get(ct)
    if not signatures:
        return False
    head = archivo.read(12)
    archivo.seek(0)  # rewind so the file can be read/saved later
    if ct == "image/webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return any(head.startswith(sig) for sig in signatures)


class CreateMensajeSerializer(serializers.Serializer):
    contenido = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    archivo = serializers.FileField(required=False)
    reply_to = serializers.IntegerField(required=False)

    def validate(self, attrs):
        contenido = attrs.get("contenido", "").strip() if attrs.get("contenido") else ""
        archivo = attrs.get("archivo")
        if not contenido and not archivo:
            raise serializers.ValidationError("El mensaje no puede estar vacio.")
        if contenido and len(contenido) > 2000:
            raise serializers.ValidationError(
                "El mensaje no puede exceder 2000 caracteres."
            )
        if archivo:
            allowed_types = [
                "image/jpeg",
                "image/png",
                "image/gif",
                "image/webp",
                "application/pdf",
                "text/plain",
            ]
            if archivo.content_type not in allowed_types:
                raise serializers.ValidationError("Tipo de archivo no permitido.")
            if archivo.size > 10 * 1024 * 1024:
                raise serializers.ValidationError("El archivo no puede exceder 10MB.")
            if not _matches_magic(archivo):
                raise serializers.ValidationError(
                    "El contenido del archivo no coincide con su tipo declarado."
                )
        return attrs

    def validate_reply_to(self, value):
        if value:
            try:
                Mensaje.objects.get(pk=value)
            except Mensaje.DoesNotExist:
                raise serializers.ValidationError(
                    "El mensaje al que respondes no existe."
                )
        return value
