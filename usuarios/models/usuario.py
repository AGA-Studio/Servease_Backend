# usuarios/models/usuario.py
from django.db import models
from .rol import Rol
from .categoria import Categoria
from .empresa import Empresa


class Usuario(models.Model):
    id_usuario = models.UUIDField(primary_key=True, editable=False)
    nombre = models.CharField(max_length=100)
    segundo_nombre = models.CharField(max_length=100, blank=True, null=True)
    apellido_pa = models.CharField(max_length=100)
    apellido_ma = models.CharField(max_length=100, blank=True, null=True)
    correo = models.EmailField(max_length=254, unique=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    url_foto_perfil = models.URLField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50, default='activo')

    rol = models.ForeignKey(
        Rol, on_delete=models.PROTECT, db_column='id_rol', related_name='usuarios'
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='id_categoria', related_name='usuarios'
    )
    empresa = models.ForeignKey(
        Empresa, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='id_empresa', related_name='usuarios'
    )

    class Meta:
        db_table = 'usuario'
        managed = False

    def __str__(self):
        return f"{self.nombre} {self.apellido_pa}"