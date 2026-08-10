from django.db import migrations

# `vista_info_aplicantes.mensaje_proveedor` estaba aliasado únicamente a
# `oferta.comentario` (el comentario de la última contraoferta). El view se
# creó antes de que existiera `postulacion.mensaje` (la carta de
# presentación con la que el proveedor se postula por primera vez) y nunca
# se actualizó — así que en cualquier postulación sin negociación todavía
# (sin filas en `oferta`), el cliente veía la tarjeta del aplicante sin
# mensaje. Se agrega COALESCE para caer al mensaje original de la
# postulación cuando aún no hay ninguna oferta/contraoferta.

FORWARD_SQL = """
CREATE OR REPLACE VIEW vista_info_aplicantes AS
 SELECT p.id_postulacion,
    p.servicio_id,
    p.fecha AS fecha_postulacion,
    e.descripcion AS estado_solicitud,
    p.precio_propuesto,
    COALESCE(o.comentario, p.mensaje) AS mensaje_proveedor,
    COALESCE(o.monto, p.precio_propuesto) AS presupuesto_acordado,
    u.id_usuario AS proveedor_id,
    (u.nombre::text || ' '::text) || u.apellido_pa::text AS nombre_proveedor,
    u.url_foto_perfil,
    round(COALESCE(r.rating_promedio, 0::numeric), 1)::double precision AS rating,
    COALESCE(r.num_reviews, 0::bigint)::integer AS num_reviews,
    COALESCE(t.trabajos_completados, 0::bigint)::integer AS trabajos_completados
   FROM postulacion p
     JOIN usuario u ON u.id_usuario = p.proveedor_id
     JOIN estado e ON e.id_estado = p.estado_id
     LEFT JOIN LATERAL ( SELECT oferta.monto,
            oferta.comentario
           FROM oferta
          WHERE oferta.postulacion_id = p.id_postulacion
          ORDER BY oferta.fecha DESC
         LIMIT 1) o ON true
     LEFT JOIN LATERAL ( SELECT avg(calificacion.puntuacion) AS rating_promedio,
            count(*) AS num_reviews
           FROM calificacion
          WHERE calificacion.evaluado_id = u.id_usuario) r ON true
     LEFT JOIN LATERAL ( SELECT count(*) AS trabajos_completados
           FROM transaccion
          WHERE transaccion.proveedor_id = u.id_usuario AND transaccion.estado::text = 'completada'::text) t ON true;
"""

REVERSE_SQL = """
CREATE OR REPLACE VIEW vista_info_aplicantes AS
 SELECT p.id_postulacion,
    p.servicio_id,
    p.fecha AS fecha_postulacion,
    e.descripcion AS estado_solicitud,
    p.precio_propuesto,
    o.comentario AS mensaje_proveedor,
    COALESCE(o.monto, p.precio_propuesto) AS presupuesto_acordado,
    u.id_usuario AS proveedor_id,
    (u.nombre::text || ' '::text) || u.apellido_pa::text AS nombre_proveedor,
    u.url_foto_perfil,
    round(COALESCE(r.rating_promedio, 0::numeric), 1)::double precision AS rating,
    COALESCE(r.num_reviews, 0::bigint)::integer AS num_reviews,
    COALESCE(t.trabajos_completados, 0::bigint)::integer AS trabajos_completados
   FROM postulacion p
     JOIN usuario u ON u.id_usuario = p.proveedor_id
     JOIN estado e ON e.id_estado = p.estado_id
     LEFT JOIN LATERAL ( SELECT oferta.monto,
            oferta.comentario
           FROM oferta
          WHERE oferta.postulacion_id = p.id_postulacion
          ORDER BY oferta.fecha DESC
         LIMIT 1) o ON true
     LEFT JOIN LATERAL ( SELECT avg(calificacion.puntuacion) AS rating_promedio,
            count(*) AS num_reviews
           FROM calificacion
          WHERE calificacion.evaluado_id = u.id_usuario) r ON true
     LEFT JOIN LATERAL ( SELECT count(*) AS trabajos_completados
           FROM transaccion
          WHERE transaccion.proveedor_id = u.id_usuario AND transaccion.estado::text = 'completada'::text) t ON true;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0007_merge_20260805_1911'),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
