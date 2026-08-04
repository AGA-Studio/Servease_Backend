from django.urls import path

from mensajeria import views

urlpatterns = [
    path(
        "conversaciones/",
        views.ConversacionListCreateView.as_view(),
        name="conversacion-list-create",
    ),
    path(
        "conversaciones/<int:id_conversacion>/",
        views.ConversacionDetailView.as_view(),
        name="conversacion-detail",
    ),
    path(
        "conversaciones/<int:id_conversacion>/mensajes/",
        views.MensajeListCreateView.as_view(),
        name="mensaje-list-create",
    ),
    path(
        "conversaciones/<int:id_conversacion>/leido/",
        views.MarcarLeidoView.as_view(),
        name="marcar-leido",
    ),
    path(
        "conversaciones/<int:id_conversacion>/typing/",
        views.ConversacionTypingView.as_view(),
        name="conversacion-typing",
    ),
    path(
        "conversaciones/<int:id_conversacion>/mensajes/<int:id_mensaje>/",
        views.MensajeDetailView.as_view(),
        name="mensaje-detail",
    ),
    path(
        "mensajes/<int:id_mensaje>/archivo/",
        views.MensajeArchivoView.as_view(),
        name="mensaje-archivo",
    ),
]
