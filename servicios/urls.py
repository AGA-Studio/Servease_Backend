from django.urls import path
from . import views

# urlpatterns = [
#     path('', views.ServicioCreateView.as_view(), name='servicio-create'),
#     path('<int:id_servicio>/detalle/', views.PostDetailsView.as_view(), name='servicio-detalle'),
#     path('<int:id_servicio>/aplicantes/', views.InfoAplicantesView.as_view(), name='servicio-aplicantes'),
# ]


urlpatterns = [
    path('', views.ServicioListView.as_view(), name='servicio-list'),
    path('crear/', views.ServicioCreateView.as_view(), name='servicio-create'),
    path('<int:id_servicio>/editar/', views.ServicioEditView.as_view(), name='servicio-edit'),
    path('<int:id_servicio>/eliminar/', views.ServicioDeleteView.as_view(), name='servicio-delete'),
    path('<int:id_servicio>/detalle/', views.PostDetailsView.as_view(), name='servicio-detalle'),
    path('<int:id_servicio>/aplicantes/', views.InfoAplicantesView.as_view(), name='servicio-aplicantes'),
    path('mis-trabajos/', views.MisTrabajosView.as_view(), name='servicio-mis-trabajos'),
    path('pendiente-calificar/', views.PendienteCalificarView.as_view(), name='servicio-pendiente-calificar'),
    path('pago/pendiente-cliente/', views.PagoPendienteClienteView.as_view(), name='pago-pendiente-cliente'),
    path('pago/<int:id_transaccion>/cancelar/', views.CancelarPagoView.as_view(), name='pago-cancelar'),
    path('pago/en-curso-proveedor/', views.PagoEnCursoProveedorView.as_view(), name='pago-en-curso-proveedor'),
    path('postulaciones/<int:id_postulacion>/aceptar/', views.AceptarPostulacionView.as_view(), name='postulacion-aceptar'),
    path('postulaciones/<int:id_postulacion>/aceptar-oferta/', views.AceptarOfertaView.as_view(), name='postulacion-aceptar-oferta'),
    path('postulaciones/<int:id_postulacion>/rechazar/', views.RechazarPostulacionView.as_view(), name='postulacion-rechazar'),
    path('postulaciones/<int:id_postulacion>/deshacer-rechazo/', views.DeshacerRechazoPostulacionView.as_view(), name='postulacion-deshacer-rechazo'),
    path('postulaciones/<int:id_postulacion>/cancelar/', views.CancelarPostulacionView.as_view(), name='postulacion-cancelar'),
    path('<int:id_servicio>/completar/', views.CompletarServicioView.as_view(), name='servicio-completar'),
    path('<int:id_servicio>/calificar/', views.CalificarServicioView.as_view(), name='servicio-calificar'),
    path('<int:id_servicio>/pago/iniciar/', views.IniciarPagoView.as_view(), name='pago-iniciar'),
    path('<int:id_servicio>/pago/pendiente/', views.PagoPendienteView.as_view(), name='pago-pendiente'),
    path('<int:id_servicio>/pago/estado/', views.PagoEstadoView.as_view(), name='pago-estado'),
    path('webhook/stripe/', views.StripeWebhookView.as_view(), name='webhook-stripe'),
    path('ofertas/crear/', views.OfertaCreateView.as_view(), name='oferta-create'),
    path('<int:id_servicio>/postular/', views.PostularServicioView.as_view(), name='servicio-postular'),
    path('conversaciones/', views.ConversacionListView.as_view(), name='conversacion-list')
]