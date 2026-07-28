from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from mensajeria.models import Bloqueo, Conversacion, Mensaje
from mensajeria.permissions import IsEmisor, IsParticipant
from mensajeria.serializers import (
    BloqueoSerializer,
    ConversacionDetailSerializer,
    ConversacionListSerializer,
    CreateConversacionSerializer,
    CreateMensajeSerializer,
    MensajeSerializer,
)
from usuarios.models import Usuario


class ConversacionListCreateView(APIView):
    """GET: list user's conversations (paginated). POST: create a new conversation."""

    permission_classes = (IsAuthenticated,)
    throttle_scope = "conversaciones.list"

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        conversations = Conversacion.objects.filter(
            Q(cliente=request.user) | Q(proveedor=request.user),
            estado="activa",
        )
        if q:
            conversations = conversations.filter(
                Q(cliente__nombre__icontains=q)
                | Q(cliente__apellido_pa__icontains=q)
                | Q(proveedor__nombre__icontains=q)
                | Q(proveedor__apellido_pa__icontains=q)
            )
        conversations = conversations.select_related(
            "cliente",
            "proveedor",
            "cliente__rol",
            "proveedor__rol",
            "cliente__categoria",
            "proveedor__categoria",
        ).order_by("-ultimo_mensaje_fecha", "-fecha_inicio")

        paginator = PageNumberPagination()
        paginator.page_size = 20
        paginator.page_size_query_param = "page_size"
        page = paginator.paginate_queryset(conversations, request)
        serializer = ConversacionListSerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CreateConversacionSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        existing = serializer.validated_data.get("existing")
        if existing:
            detail = ConversacionDetailSerializer(existing).data
            return Response(detail, status=status.HTTP_200_OK)

        conversacion = Conversacion.objects.create(
            cliente=request.user,
            proveedor_id=serializer.validated_data["proveedor_id"],
            servicio=serializer.validated_data.get("servicio"),
        )
        detail = ConversacionDetailSerializer(conversacion).data
        return Response(detail, status=status.HTTP_201_CREATED)


class ConversacionDetailView(APIView):
    """GET: conversation detail. DELETE: archive conversation."""

    permission_classes = (
        IsAuthenticated,
        IsParticipant,
    )

    def get(self, request, id_conversacion):
        conversacion = get_object_or_404(Conversacion, pk=id_conversacion)
        self.check_object_permissions(request, conversacion)
        serializer = ConversacionDetailSerializer(conversacion)
        return Response(serializer.data)

    def delete(self, request, id_conversacion):
        conversacion = get_object_or_404(Conversacion, pk=id_conversacion)
        self.check_object_permissions(request, conversacion)
        conversacion.estado = "archivada"
        conversacion.save(update_fields=["estado"])
        return Response(
            {"detail": "Conversacion archivada."},
            status=status.HTTP_200_OK,
        )


class MensajeListCreateView(APIView):
    """GET: paginated messages. POST: send message (text or file)."""

    permission_classes = (
        IsAuthenticated,
        IsParticipant,
    )
    throttle_scope = "mensajes.list"
    parser_classes = (
        MultiPartParser,
        FormParser,
        JSONParser,
    )

    def get(self, request, id_conversacion):
        conversacion = get_object_or_404(Conversacion, pk=id_conversacion)
        self.check_object_permissions(request, conversacion)

        before_id = request.query_params.get("before")
        messages = Mensaje.objects.filter(
            conversacion=conversacion, deleted_at__isnull=True
        ).select_related("emisor", "reply_to", "reply_to__emisor")

        if before_id:
            messages = messages.filter(id_mensaje__lt=before_id)

        paginator = PageNumberPagination()
        paginator.page_size = 50
        paginator.page_size_query_param = "page_size"
        page = paginator.paginate_queryset(
            messages.order_by("-fecha", "-id_mensaje"), request
        )
        page = list(reversed(page))  # chronological order
        serializer = MensajeSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, id_conversacion):
        conversacion = get_object_or_404(Conversacion, pk=id_conversacion)
        self.check_object_permissions(request, conversacion)

        serializer = CreateMensajeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check if user is blocked
        if Bloqueo.objects.filter(
            Q(usuario_bloqueador=conversacion.cliente, usuario_bloqueado=request.user)
            | Q(
                usuario_bloqueador=conversacion.proveedor,
                usuario_bloqueado=request.user,
            )
        ).exists():
            return Response(
                {"detail": "No puedes enviar mensajes en esta conversación."},
                status=status.HTTP_403_FORBIDDEN,
            )

        validated = serializer.validated_data
        reply_to_id = validated.get("reply_to")

        reply_to = None
        if reply_to_id:
            reply_to = get_object_or_404(Mensaje, pk=reply_to_id)
            if reply_to.conversacion_id != conversacion.id_conversacion:
                return Response(
                    {
                        "detail": "El mensaje al que respondes no pertenece a esta conversación."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        tipo = "archivo" if validated.get("archivo") else "texto"
        mensaje = Mensaje.objects.create(
            conversacion=conversacion,
            emisor=request.user,
            contenido=validated.get("contenido", ""),
            archivo=validated.get("archivo"),
            reply_to=reply_to,
            tipo_mensaje=tipo,
        )

        result = MensajeSerializer(mensaje, context={"request": request}).data
        return Response(result, status=status.HTTP_201_CREATED)


class MensajeDetailView(APIView):
    """GET: single message detail. PATCH: edit message (only emisor). DELETE: soft-delete message (only emisor)."""

    permission_classes = (
        IsAuthenticated,
        IsParticipant,
        IsEmisor,
    )
    throttle_scope = "mensajes.detail"

    def get(self, request, id_conversacion, id_mensaje):
        conversacion = get_object_or_404(Conversacion, pk=id_conversacion)
        self.check_object_permissions(request, conversacion)
        mensaje = get_object_or_404(
            Mensaje, pk=id_mensaje, conversacion=conversacion, deleted_at__isnull=True
        )
        self.check_object_permissions(request, mensaje)
        serializer = MensajeSerializer(mensaje, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, id_conversacion, id_mensaje):
        conversacion = get_object_or_404(Conversacion, pk=id_conversacion)
        self.check_object_permissions(request, conversacion)
        mensaje = get_object_or_404(
            Mensaje, pk=id_mensaje, conversacion=conversacion, deleted_at__isnull=True
        )
        self.check_object_permissions(request, mensaje)

        serializer = CreateMensajeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mensaje.contenido = serializer.validated_data["contenido"]
        mensaje.save(update_fields=["contenido"])

        result = MensajeSerializer(mensaje, context={"request": request}).data
        return Response(result)

    def delete(self, request, id_conversacion, id_mensaje):
        conversacion = get_object_or_404(Conversacion, pk=id_conversacion)
        self.check_object_permissions(request, conversacion)
        mensaje = get_object_or_404(
            Mensaje, pk=id_mensaje, conversacion=conversacion, deleted_at__isnull=True
        )
        self.check_object_permissions(request, mensaje)

        mensaje.deleted_at = timezone.now()
        mensaje.save(update_fields=["deleted_at"])

        return Response(status=status.HTTP_204_NO_CONTENT)


class MarcarLeidoView(APIView):
    """PATCH: mark unread messages from other user as read."""

    permission_classes = (
        IsAuthenticated,
        IsParticipant,
    )

    def patch(self, request, id_conversacion):
        conversacion = get_object_or_404(Conversacion, pk=id_conversacion)
        self.check_object_permissions(request, conversacion)

        count = (
            Mensaje.objects.filter(
                conversacion=conversacion,
                leido=False,
                deleted_at__isnull=True,
            )
            .exclude(emisor=request.user)
            .update(leido=True)
        )

        # Broadcast read_receipt via WebSocket
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"chat_{conversacion.id_conversacion}",
                {
                    "type": "read_receipt",
                    "conversacion_id": str(conversacion.id_conversacion),
                    "reader_id": str(request.user.id_usuario),
                    "count": count,
                },
            )

        return Response({"count": count})


class MensajeArchivoView(APIView):
    """GET: download message attachment."""

    permission_classes = (
        IsAuthenticated,
        IsParticipant,
    )

    def get(self, request, id_mensaje):
        mensaje = get_object_or_404(Mensaje, pk=id_mensaje, deleted_at__isnull=True)
        self.check_object_permissions(request, mensaje.conversacion)

        if not mensaje.archivo:
            raise Http404("No hay archivo adjunto.")

        file_path = mensaje.archivo.path
        if not default_storage.exists(file_path):
            raise Http404("Archivo no encontrado.")

        response = FileResponse(default_storage.open(file_path, "rb"))
        response["Content-Disposition"] = (
            f'attachment; filename="{mensaje.archivo.name}"'
        )
        return response


class BloqueoListCreateView(APIView):
    """POST: block a user. GET: list blocked users."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        bloqueado_id = request.data.get("bloqueado_id")
        _motivo = request.data.get("motivo", "")  # stored in serializer

        if not bloqueado_id:
            return Response(
                {"detail": "bloqueado_id es requerido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if str(request.user.id_usuario) == str(bloqueado_id):
            return Response(
                {"detail": "No puedes bloquearte a ti mismo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            Usuario.objects.get(id_usuario=bloqueado_id)
        except Usuario.DoesNotExist:
            return Response(
                {"detail": "Usuario no encontrado."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Check if already blocked
        if Bloqueo.objects.filter(
            usuario_bloqueador=request.user, usuario_bloqueado_id=bloqueado_id
        ).exists():
            return Response(
                {"detail": "Este usuario ya está bloqueado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bloqueo = Bloqueo.objects.create(
            usuario_bloqueador=request.user,
            usuario_bloqueado_id=bloqueado_id,
            motivo=request.data.get("motivo", ""),
        )
        serializer = BloqueoSerializer(bloqueo)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request):
        bloqueos = Bloqueo.objects.filter(
            usuario_bloqueador=request.user
        ).select_related("usuario_bloqueado")
        serializer = BloqueoSerializer(bloqueos, many=True)
        return Response(serializer.data)


class BloqueoDetailView(APIView):
    """DELETE: unblock a user."""

    permission_classes = (IsAuthenticated,)

    def delete(self, request, id_bloqueo):
        bloqueo = get_object_or_404(
            Bloqueo, pk=id_bloqueo, usuario_bloqueador=request.user
        )
        bloqueo.delete()
        return Response({"detail": "Usuario desbloqueado."}, status=status.HTTP_200_OK)
