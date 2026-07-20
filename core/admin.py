from django.contrib import admin
from .models import (
    Empresa, Sucursal, Rol, Categoria, Usuario, Servicio,
    Postulacion, Oferta, Transaccion, Conversacion, Mensaje, Calificacion
)

admin.site.register(Empresa)
admin.site.register(Sucursal)
admin.site.register(Rol)
admin.site.register(Categoria)
admin.site.register(Usuario)
admin.site.register(Servicio)
admin.site.register(Postulacion)
admin.site.register(Oferta)
admin.site.register(Transaccion)
admin.site.register(Conversacion)
admin.site.register(Mensaje)
admin.site.register(Calificacion)