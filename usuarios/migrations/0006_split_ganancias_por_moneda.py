# `vista_resumen_ganancias` sumaba `transaccion.monto`/`postulacion.precio_propuesto`
# de todas las transacciones/postulaciones del proveedor sin importar la moneda
# del servicio (`servicio.tipo_cambio`). Efecto: un proveedor con moneda MXN que
# tenía propuestas en USD veía esos dólares sumados directo como si fueran pesos.
#
# Esta vista no vive en el repo (se administra directo en Supabase, igual que
# `vista_conversaciones` / el trigger de `unread_count`), así que aquí solo se
# deja documentado y versionado el cambio: cada bucket (esta_semana, este_mes,
# pendiente, total, semana_anterior, mes_anterior) se separa en `_mxn`/`_usd`.
# El frontend (que ya integra la API de tipo de cambio vía CurrencyContext)
# convierte el bucket USD a MXN con la tasa vigente antes de sumarlos, y calcula
# `proyectado` y los `%_cambio` después de esa conversión — por eso se quitan de
# la vista, ya no se pueden calcular correctamente del lado de la base de datos
# sin una tasa de cambio persistida ahí.

from django.db import migrations, models

SQL_FORWARD = """
-- CREATE OR REPLACE VIEW no puede renombrar/quitar columnas de salida
-- (esta_semana -> esta_semana_mxn/_usd, se quitan proyectado/pct_cambio),
-- así que hay que recrearla. Sin dependientes (confirmado vía pg_depend).
DROP VIEW IF EXISTS vista_resumen_ganancias;

CREATE VIEW vista_resumen_ganancias AS
SELECT
    u.id_usuario AS proveedor_id,

    round(COALESCE(esta_semana.mxn, 0::numeric), 2) AS ganancias_esta_semana_mxn,
    round(COALESCE(esta_semana.usd, 0::numeric), 2) AS ganancias_esta_semana_usd,

    round(COALESCE(este_mes.mxn, 0::numeric), 2) AS ganancias_este_mes_mxn,
    round(COALESCE(este_mes.usd, 0::numeric), 2) AS ganancias_este_mes_usd,

    round(COALESCE(pendiente.mxn, 0::numeric), 2) AS ganancias_pendiente_mxn,
    round(COALESCE(pendiente.usd, 0::numeric), 2) AS ganancias_pendiente_usd,

    round(COALESCE(total.mxn, 0::numeric), 2) AS ganancias_totales_mxn,
    round(COALESCE(total.usd, 0::numeric), 2) AS ganancias_totales_usd,

    round(COALESCE(semana_anterior.mxn, 0::numeric), 2) AS ganancias_semana_anterior_mxn,
    round(COALESCE(semana_anterior.usd, 0::numeric), 2) AS ganancias_semana_anterior_usd,

    round(COALESCE(mes_anterior.mxn, 0::numeric), 2) AS ganancias_mes_anterior_mxn,
    round(COALESCE(mes_anterior.usd, 0::numeric), 2) AS ganancias_mes_anterior_usd

FROM usuario u
LEFT JOIN LATERAL (
    SELECT
        sum(t.monto - t.comision) FILTER (WHERE COALESCE(tc.nombre, 'MXN') = 'MXN') AS mxn,
        sum(t.monto - t.comision) FILTER (WHERE tc.nombre = 'USD') AS usd
    FROM transaccion t
    JOIN servicio sv ON sv.id_servicio = t.servicio_id
    LEFT JOIN tipo_cambio tc ON tc.id_tipo_cambio = sv.tipo_cambio_id
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
      AND t.fecha >= date_trunc('week'::text, now())
) esta_semana ON true
LEFT JOIN LATERAL (
    SELECT
        sum(t.monto - t.comision) FILTER (WHERE COALESCE(tc.nombre, 'MXN') = 'MXN') AS mxn,
        sum(t.monto - t.comision) FILTER (WHERE tc.nombre = 'USD') AS usd
    FROM transaccion t
    JOIN servicio sv ON sv.id_servicio = t.servicio_id
    LEFT JOIN tipo_cambio tc ON tc.id_tipo_cambio = sv.tipo_cambio_id
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
      AND t.fecha >= date_trunc('month'::text, now())
) este_mes ON true
LEFT JOIN LATERAL (
    SELECT
        sum(COALESCE(o.monto, p.precio_propuesto)) FILTER (WHERE COALESCE(tc.nombre, 'MXN') = 'MXN') AS mxn,
        sum(COALESCE(o.monto, p.precio_propuesto)) FILTER (WHERE tc.nombre = 'USD') AS usd
    FROM postulacion p
    JOIN servicio s ON s.id_servicio = p.servicio_id
    LEFT JOIN tipo_cambio tc ON tc.id_tipo_cambio = s.tipo_cambio_id
    LEFT JOIN LATERAL (
        SELECT oferta.monto
        FROM oferta
        WHERE oferta.postulacion_id = p.id_postulacion
        ORDER BY oferta.fecha DESC
        LIMIT 1
    ) o ON true
    WHERE p.proveedor_id = u.id_usuario
      AND p.estado_id = 1
      AND s.estado_id = 4
) pendiente ON true
LEFT JOIN LATERAL (
    SELECT
        sum(t.monto - t.comision) FILTER (WHERE COALESCE(tc.nombre, 'MXN') = 'MXN') AS mxn,
        sum(t.monto - t.comision) FILTER (WHERE tc.nombre = 'USD') AS usd
    FROM transaccion t
    JOIN servicio sv ON sv.id_servicio = t.servicio_id
    LEFT JOIN tipo_cambio tc ON tc.id_tipo_cambio = sv.tipo_cambio_id
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
) total ON true
LEFT JOIN LATERAL (
    SELECT
        sum(t.monto - t.comision) FILTER (WHERE COALESCE(tc.nombre, 'MXN') = 'MXN') AS mxn,
        sum(t.monto - t.comision) FILTER (WHERE tc.nombre = 'USD') AS usd
    FROM transaccion t
    JOIN servicio sv ON sv.id_servicio = t.servicio_id
    LEFT JOIN tipo_cambio tc ON tc.id_tipo_cambio = sv.tipo_cambio_id
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
      AND t.fecha >= (date_trunc('week'::text, now()) - '7 days'::interval)
      AND t.fecha < date_trunc('week'::text, now())
) semana_anterior ON true
LEFT JOIN LATERAL (
    SELECT
        sum(t.monto - t.comision) FILTER (WHERE COALESCE(tc.nombre, 'MXN') = 'MXN') AS mxn,
        sum(t.monto - t.comision) FILTER (WHERE tc.nombre = 'USD') AS usd
    FROM transaccion t
    JOIN servicio sv ON sv.id_servicio = t.servicio_id
    LEFT JOIN tipo_cambio tc ON tc.id_tipo_cambio = sv.tipo_cambio_id
    WHERE t.proveedor_id = u.id_usuario
      AND t.estado::text = 'completada'::text
      AND t.fecha >= (date_trunc('month'::text, now()) - '1 mon'::interval)
      AND t.fecha < date_trunc('month'::text, now())
) mes_anterior ON true
WHERE u.id_rol = 2;
"""

SQL_REVERSE = """
DROP VIEW IF EXISTS vista_resumen_ganancias;

CREATE VIEW vista_resumen_ganancias AS
 SELECT u.id_usuario AS proveedor_id,
    round(COALESCE(esta_semana.total, 0::numeric), 2) AS ganancias_esta_semana,
    round(COALESCE(este_mes.total, 0::numeric), 2) AS ganancias_este_mes,
    round(COALESCE(pendiente.total, 0::numeric), 2) AS ganancias_pendiente,
    round(COALESCE(esta_semana.total, 0::numeric) + COALESCE(pendiente.total, 0::numeric), 2) AS ganancias_proyectado,
    round(COALESCE(total.total, 0::numeric), 2) AS ganancias_totales,
        CASE
            WHEN COALESCE(semana_anterior.total, 0::numeric) = 0::numeric THEN NULL::numeric
            ELSE round((esta_semana.total - semana_anterior.total) / semana_anterior.total * 100::numeric, 1)
        END AS ganancias_esta_semana_pct_cambio,
        CASE
            WHEN COALESCE(mes_anterior.total, 0::numeric) = 0::numeric THEN NULL::numeric
            ELSE round((este_mes.total - mes_anterior.total) / mes_anterior.total * 100::numeric, 1)
        END AS ganancias_este_mes_pct_cambio
   FROM usuario u
     LEFT JOIN LATERAL ( SELECT sum(t.monto - t.comision) AS total
           FROM transaccion t
          WHERE t.proveedor_id = u.id_usuario AND t.estado::text = 'completada'::text AND t.fecha >= date_trunc('week'::text, now())) esta_semana ON true
     LEFT JOIN LATERAL ( SELECT sum(t.monto - t.comision) AS total
           FROM transaccion t
          WHERE t.proveedor_id = u.id_usuario AND t.estado::text = 'completada'::text AND t.fecha >= date_trunc('month'::text, now())) este_mes ON true
     LEFT JOIN LATERAL ( SELECT sum(COALESCE(o.monto, p.precio_propuesto)) AS total
           FROM postulacion p
             JOIN servicio s ON s.id_servicio = p.servicio_id
             LEFT JOIN LATERAL ( SELECT oferta.monto
                   FROM oferta
                  WHERE oferta.postulacion_id = p.id_postulacion
                  ORDER BY oferta.fecha DESC
                 LIMIT 1) o ON true
          WHERE p.proveedor_id = u.id_usuario AND p.estado_id = 1 AND s.estado_id = 4) pendiente ON true
     LEFT JOIN LATERAL ( SELECT sum(t.monto - t.comision) AS total
           FROM transaccion t
          WHERE t.proveedor_id = u.id_usuario AND t.estado::text = 'completada'::text) total ON true
     LEFT JOIN LATERAL ( SELECT sum(t.monto - t.comision) AS total
           FROM transaccion t
          WHERE t.proveedor_id = u.id_usuario AND t.estado::text = 'completada'::text AND t.fecha >= (date_trunc('week'::text, now()) - '7 days'::interval) AND t.fecha < date_trunc('week'::text, now())) semana_anterior ON true
     LEFT JOIN LATERAL ( SELECT sum(t.monto - t.comision) AS total
           FROM transaccion t
          WHERE t.proveedor_id = u.id_usuario AND t.estado::text = 'completada'::text AND t.fecha >= (date_trunc('month'::text, now()) - '1 mon'::interval) AND t.fecha < date_trunc('month'::text, now())) mes_anterior ON true
  WHERE u.id_rol = 2;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0005_notificacion"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # Estos 4 campos se agregaron al modelo directo (sin migración)
                # en distintos commits previos — drift preexistente, no de este
                # cambio. Se reconcilian aquí para poder quitarlos más abajo.
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_este_mes",
                    field=models.DecimalField(max_digits=12, decimal_places=2, default=0),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_totales",
                    field=models.DecimalField(max_digits=12, decimal_places=2, default=0),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_esta_semana_pct_cambio",
                    field=models.DecimalField(max_digits=10, decimal_places=1, null=True),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_este_mes_pct_cambio",
                    field=models.DecimalField(max_digits=10, decimal_places=1, null=True),
                ),
                migrations.RemoveField(
                    model_name="vistaresumenganancias",
                    name="ganancias_esta_semana",
                ),
                migrations.RemoveField(
                    model_name="vistaresumenganancias",
                    name="ganancias_este_mes",
                ),
                migrations.RemoveField(
                    model_name="vistaresumenganancias",
                    name="ganancias_pendiente",
                ),
                migrations.RemoveField(
                    model_name="vistaresumenganancias",
                    name="ganancias_proyectado",
                ),
                migrations.RemoveField(
                    model_name="vistaresumenganancias",
                    name="ganancias_totales",
                ),
                migrations.RemoveField(
                    model_name="vistaresumenganancias",
                    name="ganancias_esta_semana_pct_cambio",
                ),
                migrations.RemoveField(
                    model_name="vistaresumenganancias",
                    name="ganancias_este_mes_pct_cambio",
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_esta_semana_mxn",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_esta_semana_usd",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_este_mes_mxn",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_este_mes_usd",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_pendiente_mxn",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_pendiente_usd",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_totales_mxn",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_totales_usd",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_semana_anterior_mxn",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_semana_anterior_usd",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_mes_anterior_mxn",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
                migrations.AddField(
                    model_name="vistaresumenganancias",
                    name="ganancias_mes_anterior_usd",
                    field=models.DecimalField(max_digits=12, decimal_places=2),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=SQL_FORWARD,
                    reverse_sql=SQL_REVERSE,
                    elidable=False,
                ),
            ],
        ),
    ]
