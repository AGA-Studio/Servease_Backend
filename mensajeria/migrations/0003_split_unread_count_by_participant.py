# `unread_count` era un solo contador compartido entre cliente y proveedor,
# incrementado en cada mensaje nuevo sin importar quién lo mandaba. Efecto:
# el remitente veía el mismo badge de "no leídos" que el destinatario (p.ej.
# el proveedor veía "2 no leídos" por 2 mensajes que él mismo había enviado
# y el cliente aún no había leído). Se separa en un contador por lado y se
# actualizan los triggers para incrementar/decrementar solo el del receptor
# real de cada mensaje (columna `mensaje.receptor_id`).
#
# El SQL ya se corrió directo en el remoto (Supabase) por el equipo, igual
# que `estado_id` en la 0002 (ver SQL_CONVERT_ESTADO): por eso, como ahí,
# usamos SeparateDatabaseAndState. El SQL es idempotente (IF NOT EXISTS /
# IF EXISTS / CREATE OR REPLACE) -> no-op en el remoto ya corregido, y deja
# el esquema correcto en una BD fresca o de desarrollo.

from django.db import migrations, models

SQL_FORWARD = """
ALTER TABLE conversacion
    ADD COLUMN IF NOT EXISTS unread_count_cliente   integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS unread_count_proveedor integer NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'conversacion' AND column_name = 'unread_count'
    ) THEN
        UPDATE conversacion c
        SET unread_count_cliente = (
                SELECT COUNT(*) FROM mensaje m
                WHERE m.conversacion_id = c.id_conversacion
                  AND m.receptor_id = c.cliente_id
                  AND m.leido = FALSE
                  AND m.deleted_at IS NULL
            ),
            unread_count_proveedor = (
                SELECT COUNT(*) FROM mensaje m
                WHERE m.conversacion_id = c.id_conversacion
                  AND m.receptor_id = c.proveedor_id
                  AND m.leido = FALSE
                  AND m.deleted_at IS NULL
            );
    END IF;
END $$;

CREATE OR REPLACE FUNCTION maintain_conversacion_meta()
RETURNS TRIGGER AS $$
DECLARE
    v_cliente_id   uuid;
    v_proveedor_id uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT cliente_id, proveedor_id INTO v_cliente_id, v_proveedor_id
        FROM conversacion WHERE id_conversacion = NEW.conversacion_id;

        UPDATE conversacion
        SET unread_count_cliente   = unread_count_cliente
                                      + CASE WHEN NEW.receptor_id = v_cliente_id THEN 1 ELSE 0 END,
            unread_count_proveedor = unread_count_proveedor
                                      + CASE WHEN NEW.receptor_id = v_proveedor_id THEN 1 ELSE 0 END,
            ultimo_mensaje_preview  = LEFT(NEW.contenido, 200),
            ultimo_mensaje_fecha    = NEW.fecha
        WHERE id_conversacion = NEW.conversacion_id;
        RETURN NEW;

    ELSIF TG_OP = 'UPDATE'
          AND OLD.leido = FALSE
          AND NEW.leido = TRUE
    THEN
        SELECT cliente_id, proveedor_id INTO v_cliente_id, v_proveedor_id
        FROM conversacion WHERE id_conversacion = NEW.conversacion_id;

        UPDATE conversacion
        SET unread_count_cliente   = GREATEST(unread_count_cliente
                                      - CASE WHEN NEW.receptor_id = v_cliente_id THEN 1 ELSE 0 END, 0),
            unread_count_proveedor = GREATEST(unread_count_proveedor
                                      - CASE WHEN NEW.receptor_id = v_proveedor_id THEN 1 ELSE 0 END, 0)
        WHERE id_conversacion = NEW.conversacion_id;
        RETURN NEW;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION decrement_unread_on_soft_delete()
RETURNS TRIGGER AS $$
DECLARE
    v_cliente_id   uuid;
    v_proveedor_id uuid;
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.deleted_at IS NULL
       AND NEW.deleted_at IS NOT NULL
       AND OLD.leido = FALSE
    THEN
        SELECT cliente_id, proveedor_id INTO v_cliente_id, v_proveedor_id
        FROM conversacion WHERE id_conversacion = NEW.conversacion_id;

        UPDATE conversacion
        SET unread_count_cliente   = GREATEST(unread_count_cliente
                                      - CASE WHEN NEW.receptor_id = v_cliente_id THEN 1 ELSE 0 END, 0),
            unread_count_proveedor = GREATEST(unread_count_proveedor
                                      - CASE WHEN NEW.receptor_id = v_proveedor_id THEN 1 ELSE 0 END, 0)
        WHERE id_conversacion = NEW.conversacion_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER TABLE conversacion DROP COLUMN IF EXISTS unread_count;
"""

SQL_REVERSE = """
ALTER TABLE conversacion
    ADD COLUMN IF NOT EXISTS unread_count integer NOT NULL DEFAULT 0;

UPDATE conversacion
SET unread_count = unread_count_cliente + unread_count_proveedor;

CREATE OR REPLACE FUNCTION maintain_conversacion_meta()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE conversacion
        SET unread_count            = unread_count + 1,
            ultimo_mensaje_preview  = LEFT(NEW.contenido, 200),
            ultimo_mensaje_fecha    = NEW.fecha
        WHERE id_conversacion = NEW.conversacion_id;
        RETURN NEW;

    ELSIF TG_OP = 'UPDATE'
          AND OLD.leido = FALSE
          AND NEW.leido = TRUE
    THEN
        UPDATE conversacion
        SET unread_count = GREATEST(unread_count - 1, 0)
        WHERE id_conversacion = NEW.conversacion_id;
        RETURN NEW;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION decrement_unread_on_soft_delete()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.deleted_at IS NULL
       AND NEW.deleted_at IS NOT NULL
       AND OLD.leido = FALSE
    THEN
        UPDATE conversacion
        SET unread_count = GREATEST(unread_count - 1, 0)
        WHERE id_conversacion = NEW.conversacion_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER TABLE conversacion
    DROP COLUMN IF EXISTS unread_count_cliente,
    DROP COLUMN IF EXISTS unread_count_proveedor;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("mensajeria", "0002_add_messaging_features"),
    ]

    operations = [
        # Remoto: el SQL ya se corrió a mano -> no-op (todas las cláusulas
        # son IF NOT EXISTS / IF EXISTS / CREATE OR REPLACE). BD fresca o de
        # desarrollo: aplica el cambio completo.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="conversacion",
                    name="unread_count_cliente",
                    field=models.PositiveIntegerField(default=0),
                ),
                migrations.AddField(
                    model_name="conversacion",
                    name="unread_count_proveedor",
                    field=models.PositiveIntegerField(default=0),
                ),
                migrations.RemoveField(
                    model_name="conversacion",
                    name="unread_count",
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
