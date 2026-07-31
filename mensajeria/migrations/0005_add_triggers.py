# Generated manually — PostgreSQL triggers for mensajeria data integrity.
# These replace application-level maintenance of denormalized fields
# with atomic database guarantees (trigger-based).
#
# Triggers:
#   1. maintain_conversacion_meta → AFTER INSERT/UPDATE leido
#      Auto-updates: unread_count, ultimo_mensaje_preview, ultimo_mensaje_fecha
#   2. mark_mensaje_editado → BEFORE UPDATE contenido
#      Auto-sets editado=TRUE when content changes
#   3. validate_mensaje_insert → BEFORE INSERT
#      Rejects messages in archived conversations or from blocked users
#      Auto-defaults: estado_entrega='enviado', tipo_mensaje='texto'

from django.db import migrations

SQL_CREATE_TRIGGERS = """
-- ============================================
-- Trigger 1: Conversation metadata maintenance
-- Fires after INSERT or when leido flips to TRUE
-- ============================================
CREATE OR REPLACE FUNCTION maintain_conversacion_meta()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE conversacion
        SET unread_count      = unread_count + 1,
            ultimo_mensaje_preview = LEFT(NEW.contenido, 200),
            ultimo_mensaje_fecha   = NEW.fecha
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

DROP TRIGGER IF EXISTS trg_mensaje_conver_meta ON mensaje;
CREATE TRIGGER trg_mensaje_conver_meta
AFTER INSERT OR UPDATE OF leido ON mensaje
FOR EACH ROW EXECUTE FUNCTION maintain_conversacion_meta();


-- ============================================
-- Trigger 2: Auto-set editado on content change
-- ============================================
CREATE OR REPLACE FUNCTION mark_mensaje_editado()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.contenido IS DISTINCT FROM NEW.contenido THEN
        NEW.editado = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_mensaje_editado ON mensaje;
CREATE TRIGGER trg_mensaje_editado
BEFORE UPDATE OF contenido ON mensaje
FOR EACH ROW EXECUTE FUNCTION mark_mensaje_editado();


-- ============================================
-- Trigger 3: Validate INSERT — guard against
-- archived conversations and blocked senders.
-- Also defaults estado_entrega and tipo_mensaje.
-- ============================================
CREATE OR REPLACE FUNCTION validate_mensaje_insert()
RETURNS TRIGGER AS $$
DECLARE
    v_estado       conversacion.estado%TYPE;
    v_cliente_id   conversacion.cliente_id%TYPE;
    v_proveedor_id conversacion.proveedor_id%TYPE;
BEGIN
    SELECT estado, cliente_id, proveedor_id
    INTO v_estado, v_cliente_id, v_proveedor_id
    FROM conversacion
    WHERE id_conversacion = NEW.conversacion_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'MSG_CONV_NOT_FOUND';
    END IF;

    IF v_estado = 'archivada' THEN
        RAISE EXCEPTION 'MSG_IN_ARCHIVED';
    END IF;

    IF EXISTS (
        SELECT 1 FROM bloqueo
        WHERE (usuario_bloqueador_id = v_cliente_id
               AND usuario_bloqueado_id = NEW.emisor_id)
           OR (usuario_bloqueador_id = v_proveedor_id
               AND usuario_bloqueado_id = NEW.emisor_id)
    ) THEN
        RAISE EXCEPTION 'MSG_SENDER_BLOCKED';
    END IF;

    NEW.estado_entrega = COALESCE(NEW.estado_entrega, 'enviado');
    NEW.tipo_mensaje   = COALESCE(NEW.tipo_mensaje,   'texto');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_mensaje_validate ON mensaje;
CREATE TRIGGER trg_mensaje_validate
BEFORE INSERT ON mensaje
FOR EACH ROW EXECUTE FUNCTION validate_mensaje_insert();
"""

SQL_DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS trg_mensaje_conver_meta ON mensaje;
DROP TRIGGER IF EXISTS trg_mensaje_editado    ON mensaje;
DROP TRIGGER IF EXISTS trg_mensaje_validate   ON mensaje;

DROP FUNCTION IF EXISTS maintain_conversacion_meta();
DROP FUNCTION IF EXISTS mark_mensaje_editado();
DROP FUNCTION IF EXISTS validate_mensaje_insert();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("mensajeria", "0004_add_messaging_features"),
    ]

    operations = [
        migrations.RunSQL(
            sql=SQL_CREATE_TRIGGERS,
            reverse_sql=SQL_DROP_TRIGGERS,
            elidable=False,
        ),
    ]
