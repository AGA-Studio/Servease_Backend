from django.contrib import admin

from mensajeria.models import Conversacion, Mensaje


@admin.register(Conversacion)
class ConversacionAdmin(admin.ModelAdmin):
    list_display = (
        "id_conversacion",
        "cliente",
        "proveedor",
        "servicio",
        "estado",
        "ultimo_mensaje_fecha",
        "fecha_inicio",
    )
    list_filter = ("estado", "fecha_inicio")
    search_fields = (
        "cliente__nombre",
        "cliente__apellido_pa",
        "proveedor__nombre",
        "proveedor__apellido_pa",
        "cliente__correo",
        "proveedor__correo",
    )
    readonly_fields = ("fecha_inicio", "ultimo_mensaje_fecha")
    raw_id_fields = ("cliente", "proveedor", "servicio")
    list_select_related = ("cliente", "proveedor", "servicio")
    ordering = ("-ultimo_mensaje_fecha",)


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = (
        "id_mensaje",
        "conversacion",
        "emisor",
        "contenido_resumido",
        "fecha",
        "leido",
        "editado",
    )
    list_filter = ("leido", "editado", "fecha")
    search_fields = ("contenido",)
    readonly_fields = ("fecha",)
    raw_id_fields = ("conversacion", "emisor")
    ordering = ("-fecha",)

    @admin.display(description="contenido")
    def contenido_resumido(self, obj):
        return obj.contenido[:80] + "..." if len(obj.contenido) > 80 else obj.contenido
