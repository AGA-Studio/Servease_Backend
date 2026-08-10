from django.db import migrations

# El trigger `efectos_postulacion_aceptada` (dispara al aceptar una
# postulación) crea el chat directo con `estado_id = 7` (ABIERTO — un estado
# de Servicio, no de Conversacion). Corre DENTRO de la misma transacción que
# el UPDATE de `postulacion.estado_id`, así que se dispara antes de que
# `AceptarPostulacionView` llegue a su propio `Conversacion.objects
# .get_or_create(...)` — ese get_or_create encuentra la fila ya creada por
# el trigger y no hace nada (los `defaults` solo aplican al insertar), por
# lo que corregir el valor solo en Django nunca alcanzaba a esta fila.
# Se corrige el trigger para que use 9 (ACTIVA), el estado real de
# Conversacion (ver servicios/models/estado.py).

FORWARD_SQL = """
CREATE OR REPLACE FUNCTION public.efectos_postulacion_aceptada()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
  IF NEW.estado_id = 1 AND (OLD.estado_id IS DISTINCT FROM NEW.estado_id) THEN

    -- a) cancelar las demas postulaciones pendientes + notificarles
    WITH canceladas AS (
        UPDATE postulacion
        SET estado_id = 8 -- cancelado
        WHERE servicio_id = NEW.servicio_id
          AND id_postulacion != NEW.id_postulacion
          AND estado_id = 2 -- solo las que seguian pendientes
        RETURNING id_postulacion, proveedor_id
    )
    INSERT INTO notificacion (id_usuario, tipo, titulo, contenido, referencia_tabla, referencia_id)
    SELECT
        proveedor_id, 'postulacion', 'Postulación cancelada',
        'Tu postulación fue cancelada porque el cliente aceptó a otro proveedor',
        'postulacion', id_postulacion
    FROM canceladas;

    -- b) crear el chat para la propuesta aceptada (si no existe ya)
    INSERT INTO conversacion (fecha_inicio, estado_id, servicio_id, cliente_id, proveedor_id)
    SELECT now(), 9, NEW.servicio_id, s.cliente_id, NEW.proveedor_id
    FROM servicio s
    WHERE s.id_servicio = NEW.servicio_id
      AND NOT EXISTS (
          SELECT 1 FROM conversacion c
          WHERE c.servicio_id = NEW.servicio_id AND c.proveedor_id = NEW.proveedor_id
      );

  END IF;
  RETURN NEW;
END;
$function$
"""

REVERSE_SQL = """
CREATE OR REPLACE FUNCTION public.efectos_postulacion_aceptada()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
  IF NEW.estado_id = 1 AND (OLD.estado_id IS DISTINCT FROM NEW.estado_id) THEN

    WITH canceladas AS (
        UPDATE postulacion
        SET estado_id = 8
        WHERE servicio_id = NEW.servicio_id
          AND id_postulacion != NEW.id_postulacion
          AND estado_id = 2
        RETURNING id_postulacion, proveedor_id
    )
    INSERT INTO notificacion (id_usuario, tipo, titulo, contenido, referencia_tabla, referencia_id)
    SELECT
        proveedor_id, 'postulacion', 'Postulación cancelada',
        'Tu postulación fue cancelada porque el cliente aceptó a otro proveedor',
        'postulacion', id_postulacion
    FROM canceladas;

    INSERT INTO conversacion (fecha_inicio, estado_id, servicio_id, cliente_id, proveedor_id)
    SELECT now(), 7, NEW.servicio_id, s.cliente_id, NEW.proveedor_id
    FROM servicio s
    WHERE s.id_servicio = NEW.servicio_id
      AND NOT EXISTS (
          SELECT 1 FROM conversacion c
          WHERE c.servicio_id = NEW.servicio_id AND c.proveedor_id = NEW.proveedor_id
      );

  END IF;
  RETURN NEW;
END;
$function$
"""


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0008_fix_vista_info_aplicantes_mensaje'),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
