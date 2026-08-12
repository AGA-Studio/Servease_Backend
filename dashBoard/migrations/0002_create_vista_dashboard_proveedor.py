# `vista_dashboard_proveedor` se creo directo en Supabase (fuera de este
# repo, igual que `vista_conversaciones` / el trigger de `unread_count`) y
# nunca quedo versionada aqui. Efecto: `trabajos_activos` y
# `trabajos_completados` regresaban 0 en el endpoint
# `/api/dashboard/proveedor/{id}/` mientras que `promedio_calificacion` y
# `ganancias_totales` si funcionaban — la vista real en la BD nunca tuvo
# esas dos columnas bien calculadas (o quedaron pegadas a una definicion
# vieja). Esta migracion define (y versiona) la vista completa desde cero,
# replicando el mismo patron ya usado en otras vistas de este repo:
#
#   - "activo" = postulacion aceptada (`postulacion.estado_id = 1`,
#     ACEPTADO) cuyo servicio sigue en progreso (`servicio.estado_id = 4`,
#     PROGRESO). Mismo criterio que el bucket `pendiente` de
#     `vista_resumen_ganancias` (usuarios/migrations/0006).
#   - "completado" = transacciones completadas del proveedor
#     (`transaccion.estado = 'completada'`). Mismo criterio que
#     `trabajos_completados` en `vista_info_aplicantes`
#     (servicios/migrations/0008_fix_vista_info_aplicantes_mensaje.py).
#   - `ganancias_totales` = suma de `transaccion.monto - transaccion.comision`
#     para transacciones completadas del proveedor, igual que el bucket
#     `total` de `vista_resumen_ganancias` (sin separar por moneda, porque
#     el modelo de esta vista solo expone un campo `ganancias_totales`).
#   - `promedio_calificacion` / `num_reviews` = AVG/COUNT de
#     `calificacion` donde `evaluado_id` es el proveedor, igual que
#     `vista_info_aplicantes` y `vista_reviews_cliente`.
#
# Los campos de "semana actual vs. semana pasada" (`*_nuevos_semana`,
# `*_semana_pasada`, `*_pct_cambio`) no tenian ningun precedente encontrado
# en el repo para trabajos activos/completados, asi que se modelan con el
# mismo patron de ventana semanal (`date_trunc('week', now())`) y formula
# de `pct_cambio` (NULL si la base es 0) que ya usa `vista_resumen_ganancias`
# para las ganancias. "Nuevo esta semana" para trabajos activos se basa en
# `postulacion.fecha_actualizacion`, que el trigger de la BD actualiza
# cuando la postulacion pasa a ACEPTADO — es la fecha mas cercana a "cuando
# el trabajo se volvio activo" que existe sin agregar columnas nuevas.
# "Completado esta semana" usa `transaccion.fecha` (fecha del pago).
#
# Si estas suposiciones no coinciden con lo que el frontend espera,
# ajustar aqui — el resto del repo no tenia ninguna definicion previa de
# esta vista para comparar.

from django.db import migrations

FORWARD_SQL = """
CREATE OR REPLACE VIEW vista_dashboard_proveedor AS
SELECT
    u.id_usuario AS proveedor_id,

    COALESCE(activos.total, 0::bigint)::integer AS trabajos_activos,
    COALESCE(activos_semana.total, 0::bigint)::integer AS trabajos_activos_nuevos_semana,
    COALESCE(activos_semana_pasada.total, 0::bigint)::integer AS trabajos_activos_nuevos_semana_pasada,
    CASE
        WHEN COALESCE(activos_semana_pasada.total, 0::bigint) = 0::bigint THEN NULL::numeric
        ELSE round((activos_semana.total - activos_semana_pasada.total)::numeric / activos_semana_pasada.total::numeric * 100::numeric, 1)
    END AS trabajos_activos_pct_cambio,

    COALESCE(completados.total, 0::bigint)::integer AS trabajos_completados,
    COALESCE(completados_semana.total, 0::bigint)::integer AS completados_semana,
    COALESCE(completados_semana_pasada.total, 0::bigint)::integer AS completados_semana_pasada,
    CASE
        WHEN COALESCE(completados_semana_pasada.total, 0::bigint) = 0::bigint THEN NULL::numeric
        ELSE round((completados_semana.total - completados_semana_pasada.total)::numeric / completados_semana_pasada.total::numeric * 100::numeric, 1)
    END AS completados_pct_cambio,

    round(COALESCE(ganancias_total.total, 0::numeric), 2) AS ganancias_totales,
    round(COALESCE(ganancias_semana.total, 0::numeric), 2) AS ganancias_semana,
    round(COALESCE(ganancias_semana_pasada.total, 0::numeric), 2) AS ganancias_semana_pasada,
    CASE
        WHEN COALESCE(ganancias_semana_pasada.total, 0::numeric) = 0::numeric THEN NULL::numeric
        ELSE round((ganancias_semana.total - ganancias_semana_pasada.total) / ganancias_semana_pasada.total * 100::numeric, 1)
    END AS ganancias_pct_cambio,

    round(COALESCE(r.rating_promedio, 0::numeric), 1)::double precision AS promedio_calificacion,
    COALESCE(r.num_reviews, 0::bigint)::integer AS num_reviews

FROM usuario u

LEFT JOIN LATERAL (
    SELECT count(*) AS total
    FROM postulacion p
    JOIN servicio s ON s.id_servicio = p.servicio_id
    WHERE p.proveedor_id = u.id_usuario
      AND p.estado_id = 1
      AND s.estado_id = 4
) activos ON true

LEFT JOIN LATERAL (
    SELECT count(*) AS total
    FROM postulacion p
    JOIN servicio s ON s.id_servicio = p.servicio_id
    WHERE p.proveedor_id = u.id_usuario
      AND p.estado_id = 1
      AND s.estado_id = 4
      AND p.fecha_actualizacion >= date_trunc('week'::text, now())
) activos_semana ON true

LEFT JOIN LATERAL (
    SELECT count(*) AS total
    FROM postulacion p
    JOIN servicio s ON s.id_servicio = p.servicio_id
    WHERE p.proveedor_id = u.id_usuario
      AND p.estado_id = 1
      AND s.estado_id = 4
      AND p.fecha_actualizacion >= (date_trunc('week'::text, now()) - '7 days'::interval)
      AND p.fecha_actualizacion < date_trunc('week'::text, now())
) activos_semana_pasada ON true

LEFT JOIN LATERAL (
    SELECT count(*) AS total
    FROM transaccion t
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
) completados ON true

LEFT JOIN LATERAL (
    SELECT count(*) AS total
    FROM transaccion t
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
      AND t.fecha >= date_trunc('week'::text, now())
) completados_semana ON true

LEFT JOIN LATERAL (
    SELECT count(*) AS total
    FROM transaccion t
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
      AND t.fecha >= (date_trunc('week'::text, now()) - '7 days'::interval)
      AND t.fecha < date_trunc('week'::text, now())
) completados_semana_pasada ON true

LEFT JOIN LATERAL (
    SELECT sum(t.monto - t.comision) AS total
    FROM transaccion t
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
) ganancias_total ON true

LEFT JOIN LATERAL (
    SELECT sum(t.monto - t.comision) AS total
    FROM transaccion t
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
      AND t.fecha >= date_trunc('week'::text, now())
) ganancias_semana ON true

LEFT JOIN LATERAL (
    SELECT sum(t.monto - t.comision) AS total
    FROM transaccion t
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
      AND t.fecha >= (date_trunc('week'::text, now()) - '7 days'::interval)
      AND t.fecha < date_trunc('week'::text, now())
) ganancias_semana_pasada ON true

LEFT JOIN LATERAL (
    SELECT avg(c.puntuacion) AS rating_promedio,
           count(*) AS num_reviews
    FROM calificacion c
    WHERE c.evaluado_id = u.id_usuario
) r ON true

WHERE u.id_rol = 2;
"""

REVERSE_SQL = """
DROP VIEW IF EXISTS vista_dashboard_proveedor;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('dashBoard', '0001_initial'),
        ('usuarios', '0009_notificacion_cascade_cleanup'),
        ('servicios', '0010_servicio_trabajo_terminado'),
        ('transacciones', '0003_transaccion_stripe_payment_intent_id'),
        ('calificaciones', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
