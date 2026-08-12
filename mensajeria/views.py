import logging
import mimetypes

from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from mensajeria.models import Conversacion, Mensaje
from mensajeria.permissions import IsEmisor, IsParticipant
from mensajeria.realtime import publish_event
from mensajeria.storage import download_mensaje_archivo, upload_mensaje_archivo
from mensajeria.serializers import (
    ConversacionDetailSerializer,
    ConversacionListSerializer,
    CreateConversacionSerializer,
    CreateMensajeSerializer,
    MensajeSerializer,
)
from servicios.models.estado import ACTIVA, ARCHIVADA

logger = logging.getLogger(__name__)


class ConversacionListCreateView(APIView):
    """GET: list user's conversations (paginated). POST: create a new conversation."""

    permission_classes = (IsAuthenticated,)
    throttle_scope = "conversaciones.list"

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        # Incluye archivadas (servicio completado) para que el sidebar pueda
        # mostrarlas en su propia sección "pasados" — antes desaparecían
        # de la lista por completo al archivarse.
        conversations = Conversacion.objects.filter(
            Q(cliente=request.user) | Q(proveedor=request.user),
            estado_id__in=(ACTIVA, ARCHIVADA),
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
        ).annotate(
            ultima_actividad=Coalesce("ultimo_mensaje_fecha", "fecha_inicio"),
        ).order_by("-ultima_actividad")

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
        conversacion.estado_id = ARCHIVADA
        conversacion.save(update_fields=["estado"])
        return Response(
            {"detail": "Conversacion archivada."},
            status=status.HTTP_200_OK,
        )


class ConversacionTypingView(APIView):
    """POST: publica indicadores de escritura via Supabase Realtime.

    Body: {"action": "start" | "stop"}
    """

    permission_classes = (
        IsAuthenticated,
        IsParticipant,
    )

    def post(self, request, id_conversacion):
        conversacion = get_object_or_404(Conversacion, pk=id_conversacion)
        self.check_object_permissions(request, conversacion)

        action = request.data.get("action", "start")
        if action not in ("start", "stop"):
            return Response(
                {"detail": "action debe ser 'start' o 'stop'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        publish_event(
            conversacion.id_conversacion,
            f"typing_{action}",
            {
                "conversacion_id": conversacion.id_conversacion,
                "user_id": str(request.user.id_usuario),
                "user_name": f"{request.user.nombre} {request.user.apellido_pa}",
            },
        )
        return Response({"detail": f"typing_{action} publicado."})


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

        # Al leer la conversación, los mensajes pendientes del otro
        # participante pasan de "enviado" a "recibido" (equivalente al
        # marcado que hacía el WebSocket al conectarse).
        Mensaje.objects.filter(
            conversacion=conversacion,
            estado_entrega="enviado",
            deleted_at__isnull=True,
        ).exclude(emisor=request.user).update(estado_entrega="recibido")

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

        if conversacion.estado_id == ARCHIVADA:
            return Response(
                {"detail": "Esta conversación está archivada y no admite nuevos mensajes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateMensajeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

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

        archivo = validated.get("archivo")
        latitud = validated.get("latitud")
        longitud = validated.get("longitud")
        if latitud is not None:
            latitud = round(latitud, 6)
            longitud = round(longitud, 6)
            tipo = "ubicacion"
        elif archivo:
            tipo = "archivo"
        else:
            tipo = "texto"
        # receptor = el otro participante de la conversación (requerido por el
        # trigger remoto notificar_nuevo_mensaje() y la vista vista_conversaciones).
        receptor = (
            conversacion.proveedor
            if request.user.id_usuario == conversacion.cliente_id
            else conversacion.cliente
        )

        archivo_path = ""
        if archivo:
            try:
                archivo_path = upload_mensaje_archivo(conversacion.id_conversacion, archivo)
            except Exception:
                logger.exception(
                    "Fallo al subir adjunto a Supabase Storage (conversacion %s)",
                    conversacion.id_conversacion,
                )
                return Response(
                    {"detail": "No se pudo guardar el archivo. Intenta de nuevo."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        mensaje = Mensaje.objects.create(
            conversacion=conversacion,
            emisor=request.user,
            receptor=receptor,
            contenido=validated.get("contenido", ""),
            archivo_path=archivo_path,
            archivo_nombre=archivo.name if archivo else "",
            latitud=latitud,
            longitud=longitud,
            reply_to=reply_to,
            tipo_mensaje=tipo,
        )

        if mensaje.contenido:
            preview = mensaje.contenido[:200]
        elif tipo == "ubicacion":
            preview = "📍 Ubicación compartida"
        else:
            preview = "📎 Archivo adjunto"
        conversacion.ultimo_mensaje_preview = preview
        conversacion.ultimo_mensaje_fecha = mensaje.fecha
        conversacion.save(update_fields=["ultimo_mensaje_preview", "ultimo_mensaje_fecha"])

        result = MensajeSerializer(mensaje, context={"request": request}).data
        result["emisor_id"] = str(request.user.id_usuario)

        publish_event(
            conversacion.id_conversacion,
            "new_message",
            result,
        )
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
        mensaje.editado = True
        mensaje.save(update_fields=["contenido", "editado"])

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

        publish_event(
            conversacion.id_conversacion,
            "read_receipt",
            {
                "conversacion_id": conversacion.id_conversacion,
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

        if not mensaje.archivo_path:
            raise Http404("No hay archivo adjunto.")

        try:
            data = download_mensaje_archivo(mensaje.archivo_path)
        except Exception:
            logger.exception(
                "Fallo al descargar adjunto %s de Supabase Storage", mensaje.archivo_path
            )
            raise Http404("Archivo no encontrado.")

        filename = mensaje.archivo_nombre or "adjunto"
        content_type, _ = mimetypes.guess_type(filename)
        response = HttpResponse(data, content_type=content_type or "application/octet-stream")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
