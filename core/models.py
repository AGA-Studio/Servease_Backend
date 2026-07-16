from django.contrib.postgres.fields import ArrayField
from django.db import models


class Empresa(models.Model):
    id_empresa = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    colonia = models.CharField(max_length=150)
    calle = models.CharField(max_length=150)
    cp = models.CharField(max_length=10)
    num_int = models.CharField(max_length=10, blank=True, null=True)
    num_ext = models.CharField(max_length=10)
    estado = models.CharField(max_length=50)
    contacto = models.CharField(max_length=150)

    class Meta:
        db_table = 'empresa'

    def __str__(self):
        return self.nombre


class Sucursal(models.Model):
    id_sucursal = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    colonia = models.CharField(max_length=150)
    calle = models.CharField(max_length=150)
    cp = models.CharField(max_length=10)
    num_int = models.CharField(max_length=10, blank=True, null=True)
    num_ext = models.CharField(max_length=10)
    estado = models.CharField(max_length=50)
    contacto = models.CharField(max_length=150)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name='sucursales'
    )

    class Meta:
        db_table = 'sucursal'

    def __str__(self):
        return self.nombre


class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'rol'

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'categoria'

    def __str__(self):
        return self.nombre


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    segundo_nombre = models.CharField(max_length=100, blank=True, null=True)
    apellido_pa = models.CharField(max_length=100)
    apellido_ma = models.CharField(max_length=100, blank=True, null=True)
    correo = models.EmailField(unique=True)
    contrasena = models.CharField(max_length=255)  # guardar siempre hasheada
    celular = models.CharField(max_length=20, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50)
    rol = models.ForeignKey(
        Rol, on_delete=models.PROTECT, related_name='usuarios'
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usuarios'
    )
    empresa = models.ForeignKey(
        Empresa, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usuarios'
    )

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return f"{self.nombre} {self.apellido_pa}"


class Servicio(models.Model):
    id_servicio = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField()
    precio_inicial = models.DecimalField(max_digits=10, decimal_places=2)
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50)
    imagenes = ArrayField(
        models.CharField(max_length=255), blank=True, default=list
    )
    fecha_final = models.DateTimeField(blank=True, null=True)
    cliente = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='servicios_solicitados'
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='servicios'
    )

    class Meta:
        db_table = 'servicio'

    def __str__(self):
        return self.titulo


class Postulacion(models.Model):
    id_postulacion = models.AutoField(primary_key=True)
    fecha = models.DateTimeField(auto_now_add=True)
    precio_propuesto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=50)
    proveedor = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='postulaciones'
    )
    servicio = models.ForeignKey(
        Servicio, on_delete=models.CASCADE, related_name='postulaciones'
    )

    class Meta:
        db_table = 'postulacion'

    def __str__(self):
        return f"Postulacion {self.id_postulacion}"


class Oferta(models.Model):
    id_oferta = models.AutoField(primary_key=True)
    aceptacion = models.BooleanField(default=False)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50)
    comentario = models.TextField(blank=True, null=True)
    postulacion = models.ForeignKey(
        Postulacion, on_delete=models.CASCADE, related_name='ofertas'
    )

    class Meta:
        db_table = 'oferta'

    def __str__(self):
        return f"Oferta {self.id_oferta}"


class Transaccion(models.Model):
    id_transaccion = models.AutoField(primary_key=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    comision = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50)
    servicio = models.ForeignKey(
        Servicio, on_delete=models.CASCADE, related_name='transacciones'
    )
    proveedor = models.ForeignKey(
        Usuario, on_delete=models.PROTECT,
        related_name='transacciones_como_proveedor'
    )
    cliente = models.ForeignKey(
        Usuario, on_delete=models.PROTECT,
        related_name='transacciones_como_cliente'
    )

    class Meta:
        db_table = 'transaccion'

    def __str__(self):
        return f"Transaccion {self.id_transaccion}"


class Conversacion(models.Model):
    id_conversacion = models.AutoField(primary_key=True)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50)
    servicio = models.ForeignKey(
        Servicio, on_delete=models.CASCADE, related_name='conversaciones'
    )
    cliente = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='conversaciones_como_cliente'
    )
    proveedor = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='conversaciones_como_proveedor'
    )

    class Meta:
        db_table = 'conversacion'

    def __str__(self):
        return f"Conversacion {self.id_conversacion}"


class Mensaje(models.Model):
    id_mensaje = models.AutoField(primary_key=True)
    contenido = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)
    conversacion = models.ForeignKey(
        Conversacion, on_delete=models.CASCADE, related_name='mensajes'
    )
    emisor = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='mensajes_enviados'
    )
    receptor = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='mensajes_recibidos'
    )

    class Meta:
        db_table = 'mensaje'

    def __str__(self):
        return f"Mensaje {self.id_mensaje}"


class Calificacion(models.Model):
    id_calificacion = models.AutoField(primary_key=True)
    puntuacion = models.PositiveSmallIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField(blank=True, null=True)
    servicio = models.ForeignKey(
        Servicio, on_delete=models.CASCADE, related_name='calificaciones'
    )
    evaluador = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='calificaciones_dadas'
    )
    evaluado = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='calificaciones_recibidas'
    )

    class Meta:
        db_table = 'calificacion'

    def __str__(self):
        return f"Calificacion {self.id_calificacion}"