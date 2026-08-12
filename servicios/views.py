import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

import stripe
from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q  
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.exceptions import ValidationError
from usuarios.permissions import IsProviderRole 
from usuarios.permissions import IsClientRole
from .models import Servicio, VistaInfoAplicantes, VistaPostDetails,Postulacion,VistaConversaciones   

from calificaciones.models import Calificacion
from dashBoard.models import VistaDashboardProveedor
from mensajeria.models import Conversacion
from mensajeria.services import archivar_conversaciones_de_servicio
from transacciones.models import Transaccion
from usuarios.models import Notificacion, VistaPerfilCliente
from usuarios.permissions import IsClientRole, IsProviderRole
from .models import Oferta, Postulacion, Servicio, VistaInfoAplicantes, VistaPostDetails
from .models.estado import ABIERTO, ACEPTADO, ACTIVA, CANCELADO, COMPLETADO, PENDIENTE, PROGRESO, RECHAZADA

from .serializers import (
    CalificarServicioSerializer,
    CreateServicioSerializer,
    InfoAplicanteSerializer,
    MisTrabajosSerializer,
    OfertaSerializer,
    PostDetailsSerializer,
    ServicioListSerializer,
    ServicioSerializer,
    UpdateServicioSerializer,
    CreateOfertaSerializer,
    PostulacionSerializer,
    CreatePostulacionSerializer,
    ConversacionSerializer,
)

logger = logging.getLogger(__name__)


class ServicioCreateView(APIView):
    """Crea una nueva solicitud de servicio. Solo rol cliente."""
    permission_classes = [IsAuthenticated, IsClientRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'servicio-create'

    def post(self, request):
        serializer = CreateServicioSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        servicio = serializer.save()
        return Response(
            ServicioSerializer(servicio).data, status=status.HTTP_201_CREATED
        )


class ServicioEditView(APIView):
    """Edita una publicacion. Solo el cliente dueño, y solo si sigue 'abierto'."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def patch(self, request, id_servicio):
        servicio = get_object_or_404(Servicio, pk=id_servicio)

        if servicio.cliente_id != request.user.id_usuario:
            raise PermissionDenied('No puedes editar un servicio que no es tuyo.')
        if servicio.estado_id != ABIERTO:
            raise PermissionDenied(
                'Solo puedes editar publicaciones que sigan abiertas.'
            )

        serializer = UpdateServicioSerializer(
            servicio, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ServicioSerializer(servicio).data)


class ServicioDeleteView(APIView):
    """Cancela una publicacion (borrado logico). Solo el cliente dueño, y solo si sigue 'abierto'."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def delete(self, request, id_servicio):
        servicio = get_object_or_404(Servicio, pk=id_servicio)

        if servicio.cliente_id != request.user.id_usuario:
            raise PermissionDenied('No puedes eliminar un servicio que no es tuyo.')
        if servicio.estado_id != ABIERTO:
            raise PermissionDenied(
                'Solo puedes eliminar publicaciones que sigan abiertas.'
            )

        servicio.estado_id = CANCELADO
        servicio.save(update_fields=['estado_id'])
        return Response(
            {'detail': 'La publicación se canceló correctamente.'},
            status=status.HTTP_200_OK,
        )


class PostDetailsView(RetrieveAPIView):
    """Detalle de un servicio publicado, con la info del cliente que lo pidió."""
    permission_classes = [IsAuthenticated]
    serializer_class = PostDetailsSerializer
    queryset = VistaPostDetails.objects.all()
    lookup_field = 'id_servicio'
    lookup_url_kwarg = 'id_servicio'


class MisTrabajosView(ListAPIView):
    """Postulaciones activas (pendientes o aceptadas) del proveedor autenticado."""
    permission_classes = [IsAuthenticated, IsProviderRole]
    serializer_class = MisTrabajosSerializer

    def get_queryset(self):
        return (
            Postulacion.objects
            .filter(
                proveedor_id=self.request.user.id_usuario,
                estado_id__in=[PENDIENTE, ACEPTADO],
            )
            .select_related('servicio', 'servicio__categoria', 'servicio__tipo_cambio')
            .order_by('-fecha')
        )


class InfoAplicantesView(ListAPIView):
    """Postulaciones a un servicio. Solo el cliente dueño del servicio puede verlas."""
    permission_classes = [IsAuthenticated]
    serializer_class = InfoAplicanteSerializer

    def get_queryset(self):
        servicio_id = self.kwargs['id_servicio']
        servicio = get_object_or_404(Servicio, pk=servicio_id)
        if servicio.cliente_id != self.request.user.id_usuario:
            raise PermissionDenied(
                'No puedes ver los aplicantes de un servicio que no es tuyo.'
            )
        return VistaInfoAplicantes.objects.filter(servicio_id=servicio_id)


class ServicioFilter(django_filters.FilterSet):
    # 'estado' es FK a Estado; el filtro por texto sigue aceptando el mismo
    # query param que ya usa el frontend (?estado=abierto) mapeado a la
    # descripcion de la FK en vez de comparar el id directamente.
    estado = django_filters.CharFilter(field_name='estado__descripcion')

    class Meta:
        model = Servicio
        fields = ['categoria_id', 'estado']


class ServicioListView(ListAPIView):
    """Catalogo publico de servicios, filtrable por categoria y estado."""
    permission_classes = [AllowAny]
    serializer_class = ServicioListSerializer
    queryset = Servicio.objects.exclude(estado_id=CANCELADO).order_by('-fecha')
    filter_backends = [DjangoFilterBackend]
    filterset_class = ServicioFilter


class AceptarPostulacionView(APIView):
    """Acepta una postulación. Solo el cliente dueño del servicio, y solo si está pendiente."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def patch(self, request, id_postulacion):
        postulacion = get_object_or_404(Postulacion, pk=id_postulacion)

        if postulacion.servicio.cliente_id != request.user.id_usuario:
            raise PermissionDenied(
                'No puedes aceptar una postulación de un servicio que no es tuyo.'
            )
        if postulacion.estado_id != PENDIENTE:
            raise PermissionDenied(
                'Solo puedes aceptar postulaciones que sigan pendientes.'
            )
        if postulacion.servicio.estado_id != ABIERTO:
            raise PermissionDenied(
                'Solo puedes aceptar postulaciones de un servicio abierto.'
            )

        with transaction.atomic():
            postulacion.estado_id = ACEPTADO
            postulacion.save(update_fields=['estado_id'])

            postulacion.servicio.estado_id = PROGRESO
            postulacion.servicio.save(update_fields=['estado_id'])

            Postulacion.objects.filter(
                servicio_id=postulacion.servicio_id, estado_id=PENDIENTE
            ).exclude(pk=postulacion.pk).update(estado_id=RECHAZADA)

            Conversacion.objects.get_or_create(
                servicio_id=postulacion.servicio_id,
                cliente_id=postulacion.servicio.cliente_id,
                proveedor_id=postulacion.proveedor_id,
                defaults={'estado_id': ACTIVA},
            )

        return Response(
            {'detail': 'La postulación se aceptó correctamente.'},
            status=status.HTTP_200_OK,
        )


class RechazarPostulacionView(APIView):
    """Rechaza una postulación. Solo el cliente dueño del servicio, y solo si está pendiente."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def patch(self, request, id_postulacion):
        postulacion = get_object_or_404(Postulacion, pk=id_postulacion)

        if postulacion.servicio.cliente_id != request.user.id_usuario:
            raise PermissionDenied(
                'No puedes rechazar una postulación de un servicio que no es tuyo.'
            )
        if postulacion.estado_id != PENDIENTE:
            raise PermissionDenied(
                'Solo puedes rechazar postulaciones que sigan pendientes.'
            )

        postulacion.estado_id = RECHAZADA
        postulacion.save(update_fields=['estado_id'])
        return Response(
            {'detail': 'La postulación se rechazó correctamente.'},
            status=status.HTTP_200_OK,
        )


class DeshacerRechazoPostulacionView(APIView):
    """Deshace el rechazo de una postulación, devolviéndola a pendiente. Solo el cliente dueño del servicio."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def patch(self, request, id_postulacion):
        postulacion = get_object_or_404(Postulacion, pk=id_postulacion)

        if postulacion.servicio.cliente_id != request.user.id_usuario:
            raise PermissionDenied(
                'No puedes deshacer el rechazo de una postulación de un servicio que no es tuyo.'
            )
        if postulacion.estado_id != RECHAZADA:
            raise PermissionDenied(
                'Solo puedes deshacer el rechazo de postulaciones que estén rechazadas.'
            )
        if postulacion.servicio.estado_id != ABIERTO:
            raise PermissionDenied(
                'Solo puedes deshacer el rechazo de postulaciones de un servicio abierto.'
            )

        postulacion.estado_id = PENDIENTE
        postulacion.save(update_fields=['estado_id'])
        return Response(
            {'detail': 'El rechazo de la postulación se deshizo correctamente.'},
            status=status.HTTP_200_OK,
        )


class CancelarPostulacionView(APIView):
    """Cancela una postulación. Solo el proveedor dueño, y solo si sigue pendiente."""
    permission_classes = [IsAuthenticated, IsProviderRole]

    def patch(self, request, id_postulacion):
        postulacion = get_object_or_404(Postulacion, pk=id_postulacion)

        if postulacion.proveedor_id != request.user.id_usuario:
            raise PermissionDenied(
                'No puedes cancelar una postulación que no es tuya.'
            )
        if postulacion.estado_id != PENDIENTE:
            raise PermissionDenied(
                'Solo puedes cancelar postulaciones que sigan pendientes.'
            )

        postulacion.estado_id = CANCELADO
        postulacion.save(update_fields=['estado_id'])
        return Response(
            {'detail': 'La postulación se canceló correctamente.'},
            status=status.HTTP_200_OK,
        )


COMISION_RATE = Decimal('0.03')
PAGO_TIMEOUT = timedelta(minutes=30)


def expirar_pago_vencido(id_servicio):
    vencida = Transaccion.objects.select_for_update().filter(
        servicio_id=id_servicio, metodo_pago='tarjeta', estado='pendiente',
        fecha__lt=timezone.now() - PAGO_TIMEOUT,
    ).first()
    if vencida is None:
        return

    if vencida.stripe_payment_intent_id:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            stripe.PaymentIntent.cancel(vencida.stripe_payment_intent_id)
        except stripe.error.StripeError:
            pass

    vencida.estado = 'expirada'
    vencida.save(update_fields=['estado'])


def precio_acordado(postulacion):
    ultima_oferta = Oferta.objects.filter(
        postulacion=postulacion
    ).order_by('-fecha').first()
    monto = ultima_oferta.monto if ultima_oferta else postulacion.precio_propuesto
    if monto <= 0:
        raise PermissionDenied('El precio acordado de la postulación no es válido.')
    return monto


def calcular_comision(monto):
    return (monto * COMISION_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class MarcarTrabajoTerminadoView(APIView):
    """
    El proveedor marca el trabajo como físicamente terminado. No completa el
    servicio ni crea ningún pago o rating todavía — solo desbloquea, del
    lado del cliente, la elección de método de pago (efectivo o tarjeta).
    """
    permission_classes = [IsAuthenticated, IsProviderRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'servicio-completar'

    def post(self, request, id_servicio):
        with transaction.atomic():
            servicio = get_object_or_404(
                Servicio.objects.select_for_update(), pk=id_servicio
            )
            postulacion = Postulacion.objects.filter(
                servicio_id=id_servicio,
                proveedor_id=request.user.id_usuario,
                estado_id=ACEPTADO,
            ).first()
            if postulacion is None:
                raise PermissionDenied(
                    'No eres el proveedor asignado a este servicio.'
                )
            if servicio.estado_id != PROGRESO:
                raise PermissionDenied(
                    'Solo puedes marcar como terminado un servicio que esté '
                    'en progreso.'
                )
            if servicio.trabajo_terminado:
                raise PermissionDenied(
                    'Ya marcaste este trabajo como terminado.'
                )

            servicio.trabajo_terminado = True
            servicio.save(update_fields=['trabajo_terminado'])

        return Response(
            {'detail': 'Se avisó al cliente que el trabajo está terminado.'},
            status=status.HTTP_200_OK,
        )


class PagoEfectivoClienteView(APIView):
    """
    El cliente confirma que pagó en efectivo. Crea la transacción (monto
    calculado en el servidor, nunca confiado del cliente) y completa el
    servicio. Solo el cliente dueño, y solo si el proveedor ya marcó el
    trabajo como terminado.
    """
    permission_classes = [IsAuthenticated, IsClientRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'servicio-completar'

    def post(self, request, id_servicio):
        with transaction.atomic():
            servicio = get_object_or_404(
                Servicio.objects.select_for_update(), pk=id_servicio
            )
            if servicio.cliente_id != request.user.id_usuario:
                raise PermissionDenied(
                    'No puedes pagar un servicio que no es tuyo.'
                )
            if not servicio.trabajo_terminado:
                raise PermissionDenied(
                    'El proveedor todavía no marca este trabajo como '
                    'terminado.'
                )
            if servicio.estado_id != PROGRESO:
                raise PermissionDenied('Este servicio ya no está en progreso.')

            postulacion = Postulacion.objects.filter(
                servicio_id=id_servicio, estado_id=ACEPTADO,
            ).first()
            if postulacion is None:
                raise PermissionDenied(
                    'Este servicio no tiene un proveedor asignado.'
                )

            expirar_pago_vencido(id_servicio)

            if Transaccion.objects.filter(
                servicio_id=id_servicio, metodo_pago='tarjeta',
                estado__in=['pendiente', 'completada'],
            ).exists():
                raise PermissionDenied(
                    'Este servicio ya inició un pago con tarjeta, no '
                    'puedes pagarlo en efectivo.'
                )

            monto = precio_acordado(postulacion)
            comision = calcular_comision(monto)
            Transaccion.objects.create(
                servicio=servicio,
                cliente_id=servicio.cliente_id,
                proveedor_id=postulacion.proveedor_id,
                monto=monto,
                comision=comision,
                estado='completada',
                metodo_pago='efectivo',
            )

            servicio.estado_id = COMPLETADO
            servicio.save(update_fields=['estado_id'])
            archivar_conversaciones_de_servicio(servicio.id_servicio)

        return Response(
            {'detail': 'El servicio se completó correctamente.'},
            status=status.HTTP_200_OK,
        )


class CalificarServicioView(APIView):
    """Crea el rating del cliente hacia el proveedor. Solo el cliente dueño, y solo si el servicio está completado."""
    permission_classes = [IsAuthenticated, IsClientRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'servicio-calificar'

    def post(self, request, id_servicio):
        serializer = CalificarServicioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        puntuacion = serializer.validated_data['puntuacion']
        comentario = serializer.validated_data['comentario']

        with transaction.atomic():
            servicio = get_object_or_404(
                Servicio.objects.select_for_update(), pk=id_servicio
            )

            if servicio.cliente_id != request.user.id_usuario:
                raise PermissionDenied(
                    'No puedes calificar un servicio que no es tuyo.'
                )
            if servicio.estado_id != COMPLETADO:
                raise PermissionDenied(
                    'Solo puedes calificar un servicio que ya esté completado.'
                )

            postulacion = Postulacion.objects.filter(
                servicio_id=id_servicio, estado_id=ACEPTADO
            ).first()
            if postulacion is None:
                raise PermissionDenied(
                    'Este servicio no tiene un proveedor asignado.'
                )

            if Calificacion.objects.filter(
                servicio_id=id_servicio, evaluador_id=request.user.id_usuario
            ).exists():
                raise PermissionDenied('Ya calificaste este servicio.')

            Calificacion.objects.create(
                servicio=servicio,
                evaluador_id=request.user.id_usuario,
                evaluado_id=postulacion.proveedor_id,
                puntuacion=puntuacion,
                comentario=comentario,
            )

        return Response(
            {'detail': 'La calificación se registró correctamente.'},
            status=status.HTTP_201_CREATED,
        )


class PendienteCalificarView(APIView):
    """
    Servicio completado más reciente que el cliente autenticado aún no ha
    calificado. Se usa al cargar la app para no depender solo de Realtime
    (si el cliente entra después de que el proveedor ya completó el
    servicio, Realtime no dispara ningún evento nuevo que capturar).
    """
    permission_classes = [IsAuthenticated, IsClientRole]

    def get(self, request):
        calificados_ids = Calificacion.objects.filter(
            evaluador_id=request.user.id_usuario
        ).values_list('servicio_id', flat=True)

        servicio = (
            Servicio.objects
            .filter(cliente_id=request.user.id_usuario, estado_id=COMPLETADO)
            .exclude(id_servicio__in=calificados_ids)
            .order_by('-fecha')
            .first()
        )
        if servicio is None:
            return Response(None, status=status.HTTP_200_OK)

        postulacion = (
            Postulacion.objects
            .filter(servicio_id=servicio.id_servicio, estado_id=ACEPTADO)
            .select_related('proveedor')
            .first()
        )

        stats = (
            VistaDashboardProveedor.objects.filter(
                pk=postulacion.proveedor_id
            ).first()
            if postulacion else None
        )

        return Response({
            'id_servicio': servicio.id_servicio,
            'titulo': servicio.titulo,
            'proveedor_id': postulacion.proveedor_id if postulacion else None,
            'proveedor_nombre': (
                f"{postulacion.proveedor.nombre} {postulacion.proveedor.apellido_pa}"
                if postulacion else ''
            ),
            'proveedor_foto': (
                postulacion.proveedor.url_foto_perfil if postulacion else None
            ),
            'rating': stats.promedio_calificacion if stats else 0,
            'num_reviews': stats.num_reviews if stats else 0,
        })


class CalificarClienteView(APIView):
    """Crea el rating del proveedor hacia el cliente. Solo el proveedor
    asignado, y solo si el servicio ya está completado (pago resuelto)."""
    permission_classes = [IsAuthenticated, IsProviderRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'servicio-calificar'

    def post(self, request, id_servicio):
        serializer = CalificarServicioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        puntuacion = serializer.validated_data['puntuacion']
        comentario = serializer.validated_data['comentario']

        with transaction.atomic():
            servicio = get_object_or_404(
                Servicio.objects.select_for_update(), pk=id_servicio
            )

            postulacion = Postulacion.objects.filter(
                servicio_id=id_servicio,
                proveedor_id=request.user.id_usuario,
                estado_id=ACEPTADO,
            ).first()
            if postulacion is None:
                raise PermissionDenied(
                    'No eres el proveedor asignado a este servicio.'
                )
            if servicio.estado_id != COMPLETADO:
                raise PermissionDenied(
                    'Solo puedes calificar un servicio que ya esté completado.'
                )
            if Calificacion.objects.filter(
                servicio_id=id_servicio, evaluador_id=request.user.id_usuario
            ).exists():
                raise PermissionDenied('Ya calificaste este servicio.')

            Calificacion.objects.create(
                servicio=servicio,
                evaluador_id=request.user.id_usuario,
                evaluado_id=servicio.cliente_id,
                puntuacion=puntuacion,
                comentario=comentario,
            )

        return Response(
            {'detail': 'La calificación se registró correctamente.'},
            status=status.HTTP_201_CREATED,
        )


class PendienteCalificarProveedorView(APIView):
    """
    Servicio completado más reciente que el proveedor autenticado aún no ha
    calificado. Backstop de carga — con el nuevo flujo el pago puede
    resolverse (y completar el servicio) sin ninguna acción del proveedor en
    esa sesión, así que Realtime solo lo cubre si sigue conectado en ese
    momento.
    """
    permission_classes = [IsAuthenticated, IsProviderRole]

    def get(self, request):
        calificados_ids = Calificacion.objects.filter(
            evaluador_id=request.user.id_usuario
        ).values_list('servicio_id', flat=True)

        postulacion = (
            Postulacion.objects
            .filter(
                proveedor_id=request.user.id_usuario,
                estado_id=ACEPTADO,
                servicio__estado_id=COMPLETADO,
            )
            .exclude(servicio_id__in=calificados_ids)
            .select_related('servicio', 'servicio__cliente')
            .order_by('-servicio__fecha')
            .first()
        )
        if postulacion is None:
            return Response(None, status=status.HTTP_200_OK)

        servicio = postulacion.servicio
        stats = VistaPerfilCliente.objects.filter(pk=servicio.cliente_id).first()

        return Response({
            'id_servicio': servicio.id_servicio,
            'titulo': servicio.titulo,
            'cliente_id': servicio.cliente_id,
            'cliente_nombre': (
                f"{servicio.cliente.nombre} {servicio.cliente.apellido_pa}"
            ),
            'cliente_foto': servicio.cliente.url_foto_perfil,
            'rating': stats.rating if stats else 0,
            'num_reviews': stats.num_reviews if stats else 0,
        })


class TrabajoTerminadoPendienteView(APIView):
    """
    Servicio en progreso más reciente del cliente autenticado que el
    proveedor ya marcó como terminado y que el cliente todavía no resolvió
    (sin pago con tarjeta pendiente ni completado). Backstop de carga, igual
    que PendienteCalificarView / PagoPendienteClienteView.
    """
    permission_classes = [IsAuthenticated, IsClientRole]

    def get(self, request):
        servicio = (
            Servicio.objects
            .filter(
                cliente_id=request.user.id_usuario,
                estado_id=PROGRESO,
                trabajo_terminado=True,
            )
            .exclude(
                transacciones__metodo_pago='tarjeta',
                transacciones__estado__in=['pendiente', 'completada'],
            )
            .order_by('-fecha')
            .first()
        )
        if servicio is None:
            return Response(None, status=status.HTTP_200_OK)

        postulacion = Postulacion.objects.filter(
            servicio_id=servicio.id_servicio, estado_id=ACEPTADO,
        ).first()
        if postulacion is None:
            return Response(None, status=status.HTTP_200_OK)

        # Este endpoint es solo un backstop de carga (polling pasivo, no una
        # acción del usuario) — un monto acordado inválido (<=0) no debe
        # tumbarlo con un 403, simplemente se reporta que no hay nada
        # pendiente, igual que cuando no hay postulación.
        try:
            monto = precio_acordado(postulacion)
        except PermissionDenied:
            return Response(None, status=status.HTTP_200_OK)

        return Response({
            'id_servicio': servicio.id_servicio,
            'titulo': servicio.titulo,
            'monto': monto,
            'moneda': (
                servicio.tipo_cambio.nombre if servicio.tipo_cambio_id else 'MXN'
            ),
        })


class IniciarPagoClienteView(APIView):
    """Inicia un cobro con tarjeta. Solo el cliente dueño, y solo si el
    proveedor ya marcó el trabajo como terminado."""
    permission_classes = [IsAuthenticated, IsClientRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'pago-iniciar'

    def post(self, request, id_servicio):
        with transaction.atomic():
            servicio = get_object_or_404(
                Servicio.objects.select_for_update(), pk=id_servicio
            )

            if servicio.cliente_id != request.user.id_usuario:
                raise PermissionDenied(
                    'No puedes pagar un servicio que no es tuyo.'
                )
            if not servicio.trabajo_terminado:
                raise PermissionDenied(
                    'El proveedor todavía no marca este trabajo como '
                    'terminado.'
                )
            if servicio.estado_id != PROGRESO:
                raise PermissionDenied(
                    'Solo puedes iniciar un cobro para un servicio en progreso.'
                )

            postulacion = Postulacion.objects.filter(
                servicio_id=id_servicio, estado_id=ACEPTADO,
            ).first()
            if postulacion is None:
                raise PermissionDenied(
                    'Este servicio no tiene un proveedor asignado.'
                )

            expirar_pago_vencido(id_servicio)

            if Transaccion.objects.filter(
                servicio_id=id_servicio, metodo_pago='tarjeta',
                estado__in=['pendiente', 'completada'],
            ).exists():
                raise PermissionDenied(
                    'Ya hay un pago con tarjeta en curso o completado para '
                    'este servicio.'
                )

            monto = precio_acordado(postulacion)
            comision = calcular_comision(monto)
            moneda = (
                servicio.tipo_cambio.nombre.lower()
                if servicio.tipo_cambio_id else 'mxn'
            )

            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                intent = stripe.PaymentIntent.create(
                    amount=int(monto * 100),
                    currency=moneda,
                    metadata={
                        'id_servicio': id_servicio,
                        'id_proveedor': str(postulacion.proveedor_id),
                        'id_cliente': str(servicio.cliente_id),
                    },
                )
            except stripe.error.StripeError:
                return Response(
                    {'detail': 'No se pudo iniciar el cobro con el proveedor de pagos.'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            transaccion = Transaccion.objects.create(
                servicio=servicio,
                cliente_id=servicio.cliente_id,
                proveedor_id=postulacion.proveedor_id,
                monto=monto,
                comision=comision,
                estado='pendiente',
                metodo_pago='tarjeta',
                stripe_payment_intent_id=intent.id,
            )

        return Response(
            {
                'id_transaccion': transaccion.id_transaccion,
                'monto': transaccion.monto,
                'moneda': moneda.upper(),
                'estado': transaccion.estado,
                'client_secret': intent.client_secret,
            },
            status=status.HTTP_201_CREATED,
        )


class PagoPendienteView(APIView):
    """
    Devuelve el client_secret del cobro con tarjeta pendiente de un servicio,
    para que el cliente pueda confirmarlo con Stripe Elements. Solo el
    cliente dueño del servicio. El client_secret nunca se guarda en la BD,
    se recupera de Stripe en cada llamada.
    """
    permission_classes = [IsAuthenticated, IsClientRole]

    def get(self, request, id_servicio):
        servicio = get_object_or_404(Servicio, pk=id_servicio)
        if servicio.cliente_id != request.user.id_usuario:
            raise PermissionDenied(
                'No puedes ver el pago de un servicio que no es tuyo.'
            )

        transaccion = Transaccion.objects.select_related(
            'servicio__tipo_cambio'
        ).filter(
            servicio_id=id_servicio, cliente_id=request.user.id_usuario,
            metodo_pago='tarjeta', estado='pendiente',
            stripe_payment_intent_id__isnull=False,
        ).order_by('-fecha').first()
        if transaccion is None:
            raise Http404(
                'No hay un cobro con tarjeta pendiente para este servicio.'
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            intent = stripe.PaymentIntent.retrieve(
                transaccion.stripe_payment_intent_id
            )
        except stripe.error.StripeError:
            return Response(
                {'detail': 'No se pudo obtener el cobro con el proveedor de pagos.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            'id_transaccion': transaccion.id_transaccion,
            'monto': transaccion.monto,
            'moneda': (
                transaccion.servicio.tipo_cambio.nombre
                if transaccion.servicio.tipo_cambio_id else 'MXN'
            ),
            'client_secret': intent.client_secret,
        })


class PagoPendienteClienteView(APIView):
    """
    Cobro con tarjeta pendiente (o recién rechazado, pero aún retomable) más
    reciente del cliente autenticado, sin necesidad de conocer el
    id_servicio de antemano. Se usa al cargar la app para no depender solo
    de Realtime (si el proveedor inicia el cobro antes de que el cliente
    esté conectado, el INSERT ya pasó y no hay evento que capturar al
    reconectarse). Un rechazo previo no es terminal — el mismo intent sigue
    aceptando otra tarjeta, así que también se retoma.
    """
    permission_classes = [IsAuthenticated, IsClientRole]

    def get(self, request):
        transaccion = (
            Transaccion.objects
            .filter(
                cliente_id=request.user.id_usuario,
                metodo_pago='tarjeta', estado__in=['pendiente', 'rechazada'],
                stripe_payment_intent_id__isnull=False,
            )
            .select_related('servicio__tipo_cambio')
            .order_by('-fecha')
            .first()
        )
        if transaccion is None:
            return Response(None, status=status.HTTP_200_OK)

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            intent = stripe.PaymentIntent.retrieve(
                transaccion.stripe_payment_intent_id
            )
        except stripe.error.StripeError:
            return Response(
                {'detail': 'No se pudo obtener el cobro con el proveedor de pagos.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            'id_servicio': transaccion.servicio_id,
            'titulo': transaccion.servicio.titulo,
            'id_transaccion': transaccion.id_transaccion,
            'monto': transaccion.monto,
            'moneda': (
                transaccion.servicio.tipo_cambio.nombre
                if transaccion.servicio.tipo_cambio_id else 'MXN'
            ),
            'client_secret': intent.client_secret,
        })


class CancelarPagoView(APIView):
    """
    El proveedor cancela un cobro con tarjeta que sigue pendiente (mientras
    espera a que el cliente pague). Cancela el PaymentIntent en Stripe y
    marca la transacción como 'cancelada'; el cliente se entera vía Realtime
    (UPDATE en transaccion) si tenía el modal de pago abierto.
    """
    permission_classes = [IsAuthenticated, IsProviderRole]

    def post(self, request, id_transaccion):
        transaccion = get_object_or_404(Transaccion, pk=id_transaccion)

        if transaccion.proveedor_id != request.user.id_usuario:
            raise PermissionDenied(
                'No puedes cancelar un cobro que no es tuyo.'
            )
        if transaccion.metodo_pago != 'tarjeta' or transaccion.estado != 'pendiente':
            raise PermissionDenied(
                'Solo puedes cancelar un cobro con tarjeta que siga pendiente.'
            )

        if transaccion.stripe_payment_intent_id:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                stripe.PaymentIntent.cancel(transaccion.stripe_payment_intent_id)
            except stripe.error.StripeError:
                pass

        transaccion.estado = 'cancelada'
        transaccion.save(update_fields=['estado'])

        return Response(
            {'detail': 'El cobro se canceló correctamente.'},
            status=status.HTTP_200_OK,
        )


class PagoEstadoView(APIView):
    """
    Estado real del cobro con tarjeta más reciente de un servicio, para el
    proveedor asignado. Se consulta al reabrir el flujo de completar
    servicio para no depender solo de Realtime: si el proveedor recargó la
    página o navegó fuera mientras esperaba, pierde la suscripción en vivo y
    de otra forma se quedaría esperando un evento que ya pasó.
    """
    permission_classes = [IsAuthenticated, IsProviderRole]

    def get(self, request, id_servicio):
        postulacion = Postulacion.objects.filter(
            servicio_id=id_servicio,
            proveedor_id=request.user.id_usuario,
            estado_id=ACEPTADO,
        ).first()
        if postulacion is None:
            raise PermissionDenied(
                'No eres el proveedor asignado a este servicio.'
            )

        transaccion = (
            Transaccion.objects
            .select_related('servicio__tipo_cambio')
            .filter(servicio_id=id_servicio, metodo_pago='tarjeta')
            .order_by('-fecha')
            .first()
        )
        if transaccion is None:
            return Response(None, status=status.HTTP_200_OK)

        return Response({
            'id_transaccion': transaccion.id_transaccion,
            'monto': transaccion.monto,
            'moneda': (
                transaccion.servicio.tipo_cambio.nombre
                if transaccion.servicio.tipo_cambio_id else 'MXN'
            ),
            'estado': transaccion.estado,
        })


class PagoEnCursoProveedorView(APIView):
    """
    Cobro con tarjeta en curso (o recién resuelto) más reciente del
    proveedor autenticado, sin necesitar saber el id_servicio de antemano.
    Se usa al cargar "Mis Trabajos" para retomar el modal de espera o de
    calificación automáticamente si el proveedor cerró la pestaña o
    navegó fuera mientras esperaba.
    """
    permission_classes = [IsAuthenticated, IsProviderRole]

    def get(self, request):
        transaccion = (
            Transaccion.objects
            .filter(proveedor_id=request.user.id_usuario, metodo_pago='tarjeta')
            .exclude(servicio__estado_id=COMPLETADO)
            # 'cancelada' ya está resuelta (el proveedor la cerró o expiró) —
            # no hay nada que retomar. Sin este exclude, un servicio con una
            # tarjeta cancelada pero que sigue en progreso (el trabajo aún no
            # se vuelve a marcar como terminado) reabre el modal de "esperando
            # pago" en cada carga de "Mis Trabajos" y el proveedor ya no puede
            # cancelarla porque el backend correctamente rechaza cancelar algo
            # que no está pendiente.
            .exclude(estado='cancelada')
            .select_related('servicio__tipo_cambio')
            .order_by('-fecha')
            .first()
        )
        if transaccion is None:
            return Response(None, status=status.HTTP_200_OK)

        return Response({
            'id_servicio': transaccion.servicio_id,
            'id_transaccion': transaccion.id_transaccion,
            'monto': transaccion.monto,
            'moneda': (
                transaccion.servicio.tipo_cambio.nombre
                if transaccion.servicio.tipo_cambio_id else 'MXN'
            ),
            'estado': transaccion.estado,
        })


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    """
    Recibe eventos de Stripe (payment_intent.succeeded / .payment_failed) y
    actualiza la transacción correspondiente. Verifica la firma del evento
    con STRIPE_WEBHOOK_SECRET; nadie más puede aprobar/rechazar un pago.
    """

    def post(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return HttpResponse(status=400)

        event_type = event['type']
        if event_type not in ('payment_intent.succeeded', 'payment_intent.payment_failed'):
            return HttpResponse(status=200)

        intent = event['data']['object']

        with transaction.atomic():
            if event_type == 'payment_intent.succeeded':
                # El intent puede haber sido reintentado tras uno o varios
                # rechazos previos (Stripe permite confirmar el mismo intent
                # con otra tarjeta cuantas veces haga falta), así que el
                # éxito manda sin importar el estado local actual — EXCEPTO
                # 'expirada': ese estado significa que expirar_pago_vencido()
                # ya le avisó al cliente que puede pagar por otra vía (p.ej.
                # efectivo), así que si un webhook tardío llega para un
                # intent que ya dimos por perdido, no lo resucitamos (eso
                # duplicaría el ingreso si el cliente ya pagó en efectivo).
                # stripe_payment_intent_id es unique, así que esto es 0 o 1
                # fila — sin loop.
                t = Transaccion.objects.filter(
                    stripe_payment_intent_id=intent['id'],
                ).exclude(estado__in=['completada', 'expirada']).first()

                if t is None:
                    logger.warning(
                        'payment_intent.succeeded para intent %s sin '
                        'transacción local actualizable (ya completada, '
                        'expirada, o no encontrada) — requiere revisión '
                        'manual si Stripe sí capturó el pago.',
                        intent['id'],
                    )
                else:
                    # Mismo orden de locks que PagoEfectivoClienteView /
                    # IniciarPagoClienteView (Servicio primero, luego
                    # Transaccion vía expirar_pago_vencido) — invertirlo aquí
                    # podía producir un deadlock si ambos caminos corrían en
                    # paralelo sobre el mismo servicio.
                    servicio = Servicio.objects.select_for_update().filter(
                        pk=t.servicio_id,
                    ).first()
                    t = Transaccion.objects.select_for_update().get(pk=t.pk)

                    t.estado = 'completada'
                    t.save(update_fields=['estado'])

                    # El pago con tarjeta es lo que completa el servicio —
                    # antes esto pasaba solo cuando el proveedor calificaba;
                    # ahora se completa aquí mismo para que ambos lados vean
                    # el modal de calificación al mismo tiempo, vía Realtime.
                    if servicio is not None and servicio.estado_id == PROGRESO:
                        servicio.estado_id = COMPLETADO
                        servicio.save(update_fields=['estado_id'])
                        archivar_conversaciones_de_servicio(servicio.id_servicio)
                    elif servicio is not None:
                        logger.warning(
                            'payment_intent.succeeded: transacción %s '
                            'marcada completada pero el servicio %s no '
                            'estaba en PROGRESO (estado_id=%s) — no se '
                            'completó automáticamente.',
                            t.pk, servicio.id_servicio, servicio.estado_id,
                        )
            else:
                # Un rechazo NO es terminal: el intent sigue vivo y el
                # cliente puede reintentar con otra tarjeta en el mismo
                # formulario. El proveedor no se entera de esto — solo le
                # importa el resultado final (éxito o expiración real).
                Transaccion.objects.select_for_update().filter(
                    stripe_payment_intent_id=intent['id'], estado='pendiente',
                ).update(estado='rechazada')

        return HttpResponse(status=200)
class OfertaCreateView(APIView):
    """Envia una oferta/contraoferta. Solo cliente dueño o proveedor de la postulacion."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'oferta-create'

    def post(self, request):
        serializer = CreateOfertaSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        oferta = serializer.save()
        return Response(OfertaSerializer(oferta).data, status=status.HTTP_201_CREATED)


class AceptarOfertaView(APIView):
    """Acepta el monto de la última oferta de una postulación, sin aceptar
    la postulación en sí — solo la contraparte de quien mandó esa oferta
    puede aceptarla (si la mandó el cliente, solo el proveedor; y viceversa).
    Deja la postulación pendiente: es el cliente quien, con la oferta ya
    aceptada, confirma para asignar el trabajo vía AceptarPostulacionView."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, id_postulacion):
        postulacion = get_object_or_404(Postulacion, pk=id_postulacion)
        cliente_id = postulacion.servicio.cliente_id
        proveedor_id = postulacion.proveedor_id
        usuario = request.user

        if usuario.id_usuario not in (cliente_id, proveedor_id):
            raise PermissionDenied('No puedes aceptar una oferta de una postulación que no te pertenece.')
        if postulacion.estado_id != PENDIENTE:
            raise PermissionDenied('Solo puedes aceptar ofertas de postulaciones que sigan pendientes.')

        ultima_oferta = postulacion.ofertas.order_by('-fecha').first()
        if not ultima_oferta:
            raise ValidationError('No hay ninguna oferta que aceptar.')
        if ultima_oferta.emisor_id == usuario.id_usuario:
            raise PermissionDenied('No puedes aceptar tu propia oferta.')
        if ultima_oferta.aceptacion:
            raise ValidationError('Esta oferta ya fue aceptada.')

        ultima_oferta.aceptacion = True
        ultima_oferta.save(update_fields=['aceptacion'])

        contexto_rol = 'client' if ultima_oferta.emisor_id == cliente_id else 'provider'
        Notificacion.objects.create(
            usuario_id=ultima_oferta.emisor_id,
            tipo='oferta_aceptada',
            titulo='Tu oferta fue aceptada',
            contenido=(
                f'Tu propuesta de ${ultima_oferta.monto} para "{postulacion.servicio.titulo}" '
                'fue aceptada. Ya se puede confirmar para asignar el trabajo.'
            ),
            leido=False,
            fecha=timezone.now(),
            referencia_tabla='postulacion',
            referencia_id=postulacion.id_postulacion,
            contexto_rol=contexto_rol,
        )

        return Response(OfertaSerializer(ultima_oferta).data, status=status.HTTP_200_OK)


class PostularServicioView(APIView):
    """Un proveedor se postula a un servicio abierto."""
    permission_classes = [IsAuthenticated, IsProviderRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'postulacion-create'
 
    def post(self, request, id_servicio):
        servicio = get_object_or_404(Servicio, pk=id_servicio)
 
        if servicio.estado_id != ABIERTO:
            raise ValidationError('Este servicio ya no acepta postulaciones.')
 
        if servicio.cliente_id == request.user.id_usuario:
            raise PermissionDenied('No puedes postularte a tu propio servicio.')
 
        if Postulacion.objects.filter(servicio=servicio, proveedor=request.user).exists():
            raise ValidationError('Ya te postulaste a este servicio.')
 
        serializer = CreatePostulacionSerializer(
            data=request.data,
            context={'request': request, 'servicio': servicio}
        )
        serializer.is_valid(raise_exception=True)
        postulacion = serializer.save()
        return Response(
            PostulacionSerializer(postulacion).data, status=status.HTTP_201_CREATED
        )

    
class ConversacionListView(ListAPIView):
    """Conversaciones del usuario autenticado (como cliente o como proveedor),
    con el ultimo mensaje y el conteo de no leidos. Mas recientes primero."""
    permission_classes = [IsAuthenticated]
    serializer_class = ConversacionSerializer
 
    def get_queryset(self):
        usuario_id = self.request.user.id_usuario
        return VistaConversaciones.objects.filter(
            Q(cliente_id=usuario_id) | Q(proveedor_id=usuario_id)
        ).order_by('-fecha_ultimo_mensaje')
 
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
