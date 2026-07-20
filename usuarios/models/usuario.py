from django.db import models
from .rol import Rol
from .categoria import Categoria
from .empresa import Empresa


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    supabase_uid = models.UUIDField(unique=True, db_index=True)  # vincula con auth.users de Supabase
    nombre = models.CharField(max_length=100)
    segundo_nombre = models.CharField(max_length=100, blank=True, null=True)
    apellido_pa = models.CharField(max_length=100)
    apellido_ma = models.CharField(max_length=100, blank=True, null=True)
    correo = models.EmailField(unique=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name='usuarios')
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return f"{self.nombre} {self.apellido_pa}"