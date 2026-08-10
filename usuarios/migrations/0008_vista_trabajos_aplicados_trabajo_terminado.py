# Expone servicio.trabajo_terminado en vista_trabajos_aplicados para que
# "Mis Trabajos" (proveedor) sepa si ya marco un trabajo como terminado y
# esta esperando a que el cliente elija metodo de pago.

from django.db import migrations, models

FORWARD_SQL = """
CREATE OR REPLACE VIEW vista_trabajos_aplicados AS
 SELECT p.id_postulacion,
    p.proveedor_id,
    s.id_servicio,
    s.titulo,
    p.estado_id,
    e.descripcion AS estado,
    cat.id_categoria AS categoria_id,
    cat.nombre AS categoria,
    s.fecha AS fecha_publicacion,
    now() - s.fecha AS tiempo_transcurrido,
    COALESCE(o.monto, p.precio_propuesto) AS precio_final,
        CASE
            WHEN array_length(s.imagenes, 1) > 0 THEN s.imagenes[1]
            ELSE NULL::character varying
        END AS foto,
    s.trabajo_terminado
   FROM postulacion p
     JOIN servicio s ON s.id_servicio = p.servicio_id
     JOIN categoria cat ON cat.id_categoria = s.categoria_id
     JOIN estado e ON e.id_estado = p.estado_id
     LEFT JOIN LATERAL ( SELECT oferta.monto
           FROM oferta
          WHERE oferta.postulacion_id = p.id_postulacion
          ORDER BY oferta.fecha DESC
         LIMIT 1) o ON true;
"""

REVERSE_SQL = """
CREATE OR REPLACE VIEW vista_trabajos_aplicados AS
 SELECT p.id_postulacion,
    p.proveedor_id,
    s.id_servicio,
    s.titulo,
    p.estado_id,
    e.descripcion AS estado,
    cat.id_categoria AS categoria_id,
    cat.nombre AS categoria,
    s.fecha AS fecha_publicacion,
    now() - s.fecha AS tiempo_transcurrido,
    COALESCE(o.monto, p.precio_propuesto) AS precio_final,
        CASE
            WHEN array_length(s.imagenes, 1) > 0 THEN s.imagenes[1]
            ELSE NULL::character varying
        END AS foto
   FROM postulacion p
     JOIN servicio s ON s.id_servicio = p.servicio_id
     JOIN categoria cat ON cat.id_categoria = s.categoria_id
     JOIN estado e ON e.id_estado = p.estado_id
     LEFT JOIN LATERAL ( SELECT oferta.monto
           FROM oferta
          WHERE oferta.postulacion_id = p.id_postulacion
          ORDER BY oferta.fecha DESC
         LIMIT 1) o ON true;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0007_fix_vista_home_cliente_estado"),
        ("servicios", "0010_servicio_trabajo_terminado"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="vistatrabajosaplicados",
                    name="trabajo_terminado",
                    field=models.BooleanField(default=False),
                ),
            ],
            database_operations=[
                migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
            ],
        ),
    ]
