from django.db import migrations

SQL_CREATE_TRIGGER = """
-- Soft-delete: when an unread message is archived (deleted_at set),
-- decrement the conversation unread_count so the counter stays accurate.
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

DROP TRIGGER IF EXISTS trg_mensaje_softdelete_unread ON mensaje;
CREATE TRIGGER trg_mensaje_softdelete_unread
AFTER UPDATE OF deleted_at ON mensaje
FOR EACH ROW EXECUTE FUNCTION decrement_unread_on_soft_delete();
"""

SQL_DROP_TRIGGER = """
DROP TRIGGER IF EXISTS trg_mensaje_softdelete_unread ON mensaje;
DROP FUNCTION IF EXISTS decrement_unread_on_soft_delete();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("mensajeria", "0006_cleanup_post_refactor"),
    ]

    operations = [
        migrations.RunSQL(
            sql=SQL_CREATE_TRIGGER,
            reverse_sql=SQL_DROP_TRIGGER,
            elidable=False,
        ),
    ]
