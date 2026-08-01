from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

import stripe
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle

from calificaciones.models import Calificacion
from mensajeria.models import Conversacion
from transacciones.models import Transaccion
from usuarios.permissions import IsClientRole, IsProviderRole
from .models import Oferta, Postulacion, Servicio, VistaInfoAplicantes, VistaPostDetails
from .models.estado import ABIERTO as ESTADO_ABIERTO
from .serializers import (
    CalificarServicioSerializer,
    CompletarServicioSerializer,
    CreateServicioSerializer,
    InfoAplicanteSerializer,
    PostDetailsSerializer,
    ServicioListSerializer,
    ServicioSerializer,
    UpdateServicioSerializer,
)

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
        if servicio.estado != 'abierto':
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
        if servicio.estado != 'abierto':
            raise PermissionDenied(
                'Solo puedes eliminar publicaciones que sigan abiertas.'
            )

        servicio.estado = 'cancelado'
        servicio.save(update_fields=['estado'])
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


class ServicioListView(ListAPIView):
    """Catalogo publico de servicios, filtrable por categoria y estado."""
    permission_classes = [AllowAny]
    serializer_class = ServicioListSerializer
    queryset = Servicio.objects.exclude(estado='cancelado').order_by('-fecha')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['categoria_id', 'estado']


class AceptarPostulacionView(APIView):
    """Acepta una postulación. Solo el cliente dueño del servicio, y solo si está pendiente."""
    permission_classes = [IsAuthenticated, IsClientRole]

    def patch(self, request, id_postulacion):
        postulacion = get_object_or_404(Postulacion, pk=id_postulacion)

        if postulacion.servicio.cliente_id != request.user.id_usuario:
            raise PermissionDenied(
                'No puedes aceptar una postulación de un servicio que no es tuyo.'
            )
        if postulacion.estado != 'pendiente':
            raise PermissionDenied(
                'Solo puedes aceptar postulaciones que sigan pendientes.'
            )
        if postulacion.servicio.estado != 'abierto':
            raise PermissionDenied(
                'Solo puedes aceptar postulaciones de un servicio abierto.'
            )

        with transaction.atomic():
            postulacion.estado = 'aceptada'
            postulacion.save(update_fields=['estado'])

            postulacion.servicio.estado = 'progreso'
            postulacion.servicio.save(update_fields=['estado'])

            Postulacion.objects.filter(
                servicio_id=postulacion.servicio_id, estado='pendiente'
            ).exclude(pk=postulacion.pk).update(estado='rechazada')

            Conversacion.objects.get_or_create(
                servicio_id=postulacion.servicio_id,
                cliente_id=postulacion.servicio.cliente_id,
                proveedor_id=postulacion.proveedor_id,
                defaults={'estado_id': ESTADO_ABIERTO},
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
        if postulacion.estado != 'pendiente':
            raise PermissionDenied(
                'Solo puedes rechazar postulaciones que sigan pendientes.'
            )

        postulacion.estado = 'rechazada'
        postulacion.save(update_fields=['estado'])
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
        if postulacion.estado != 'rechazada':
            raise PermissionDenied(
                'Solo puedes deshacer el rechazo de postulaciones que estén rechazadas.'
            )
        if postulacion.servicio.estado != 'abierto':
            raise PermissionDenied(
                'Solo puedes deshacer el rechazo de postulaciones de un servicio abierto.'
            )

        postulacion.estado = 'pendiente'
        postulacion.save(update_fields=['estado'])
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
        if postulacion.estado != 'pendiente':
            raise PermissionDenied(
                'Solo puedes cancelar postulaciones que sigan pendientes.'
            )

        postulacion.estado = 'cancelada'
        postulacion.save(update_fields=['estado'])
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


class CompletarServicioView(APIView):
    """
    Marca un servicio como completado y crea el rating del proveedor hacia el
    cliente. Solo el proveedor asignado (postulación aceptada), y solo si el
    servicio sigue en progreso.

    Efectivo: crea la transacción aquí mismo (monto calculado en el servidor,
    nunca confiado del cliente).
    Tarjeta: exige que ya exista una transacción de tarjeta 'completada' para
    este servicio (creada por el flujo de pago), es decir que el pago ya se
    haya resuelto como aprobado antes de poder completar.
    """
    permission_classes = [IsAuthenticated, IsProviderRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'servicio-completar'

    def post(self, request, id_servicio):
        serializer = CompletarServicioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        metodo_pago = serializer.validated_data['metodo_pago']
        puntuacion = serializer.validated_data['puntuacion']
        comentario = serializer.validated_data['comentario']

        with transaction.atomic():
            servicio = get_object_or_404(
                Servicio.objects.select_for_update(), pk=id_servicio
            )

            postulacion = Postulacion.objects.filter(
                servicio_id=id_servicio,
                proveedor_id=request.user.id_usuario,
                estado='aceptada',
            ).first()
            if postulacion is None:
                raise PermissionDenied(
                    'No eres el proveedor asignado a este servicio.'
                )
            if servicio.estado != 'progreso':
                raise PermissionDenied(
                    'Solo puedes completar un servicio que esté en progreso.'
                )
            if Calificacion.objects.filter(
                servicio_id=id_servicio, evaluador_id=request.user.id_usuario
            ).exists():
                raise PermissionDenied('Ya calificaste este servicio.')

            expirar_pago_vencido(id_servicio)

            if metodo_pago == 'efectivo':
                if Transaccion.objects.filter(
                    servicio_id=id_servicio, metodo_pago='tarjeta',
                    estado__in=['pendiente', 'completada'],
                ).exists():
                    raise PermissionDenied(
                        'Este servicio ya inició un pago con tarjeta, no '
                        'puedes completarlo como efectivo.'
                    )

                monto = precio_acordado(postulacion)
                comision = calcular_comision(monto)
                Transaccion.objects.create(
                    servicio=servicio,
                    cliente_id=servicio.cliente_id,
                    proveedor_id=request.user.id_usuario,
                    monto=monto,
                    comision=comision,
                    estado='completada',
                    metodo_pago='efectivo',
                )
            else:
                pago_completado = Transaccion.objects.filter(
                    servicio_id=id_servicio,
                    proveedor_id=request.user.id_usuario,
                    metodo_pago='tarjeta',
                    estado='completada',
                ).exists()
                if not pago_completado:
                    raise PermissionDenied(
                        'El pago con tarjeta todavía no se ha completado.'
                    )

            Calificacion.objects.create(
                servicio=servicio,
                evaluador_id=request.user.id_usuario,
                evaluado_id=servicio.cliente_id,
                puntuacion=puntuacion,
                comentario=comentario,
            )

            servicio.estado = 'completado'
            servicio.save(update_fields=['estado'])

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
            if servicio.estado != 'completado':
                raise PermissionDenied(
                    'Solo puedes calificar un servicio que ya esté completado.'
                )

            postulacion = Postulacion.objects.filter(
                servicio_id=id_servicio, estado='aceptada'
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


class IniciarPagoView(APIView):
    """Inicia un cobro con tarjeta. Solo el proveedor asignado, y solo si el servicio está en progreso."""
    permission_classes = [IsAuthenticated, IsProviderRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'pago-iniciar'

    def post(self, request, id_servicio):
        with transaction.atomic():
            servicio = get_object_or_404(
                Servicio.objects.select_for_update(), pk=id_servicio
            )

            postulacion = Postulacion.objects.filter(
                servicio_id=id_servicio,
                proveedor_id=request.user.id_usuario,
                estado='aceptada',
            ).first()
            if postulacion is None:
                raise PermissionDenied(
                    'No eres el proveedor asignado a este servicio.'
                )
            if servicio.estado != 'progreso':
                raise PermissionDenied(
                    'Solo puedes iniciar un cobro para un servicio en progreso.'
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
                        'id_proveedor': str(request.user.id_usuario),
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
                proveedor_id=request.user.id_usuario,
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
                'estado': transaccion.estado,
                'client_secret': intent.client_secret,
            },
            status=status.HTTP_201_CREATED,
        )


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
        nuevo_estado = (
            'completada' if event_type == 'payment_intent.succeeded' else 'rechazada'
        )

        with transaction.atomic():
            Transaccion.objects.select_for_update().filter(
                stripe_payment_intent_id=intent['id'], estado='pendiente',
            ).update(estado=nuevo_estado)

        return HttpResponse(status=200)