# Squash de las antiguas 0002-0008 en UNA migración puramente ADITIVA.
#
# El remoto (Supabase) tiene aplicada SOLO `mensajeria 0001_initial` (el 0001
# original: estado varchar, sin columnas denormalizadas) y su esquema real ya
# fue llevado por SQL directo del equipo a: receptor_id NOT NULL, estado_id FK,
# índices de FK. Esta migración agrega lo que el modelo final necesita SIN
# tocar nada existente:
#   - NO RemoveField(receptor)            (receptor vive en el 0001 original)
#   - estado -> FK vía SeparateDatabaseAndState: en remoto la columna estado_id
#     ya existe (no-op); en BD frescas convierte la columna varchar 'estado'.
#   - NO toca el trigger on_mensaje_creado del remoto (usa trg_mensaje_*).
# Triggers: validate_mensaje_insert usa estado_id (columna real del remoto).

import django.db.models.deletion
from django.db import migrations, models


SQL_CONVERT_ESTADO = """
-- Solo actúa en BD frescas (o DBs que aún tengan la columna varchar 'estado').
-- En el remoto: estado_id ya existe -> no-op.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'conversacion' AND column_name = 'estado_id'
    ) THEN
        ALTER TABLE conversacion ADD COLUMN estado_id integer;
    END IF;
END $$;

-- Migrar valores desde la columna varchar si existe (estado original del 0001).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'conversacion' AND column_name = 'estado'
    ) THEN
        UPDATE conversacion
        SET estado_id = CASE
            WHEN estado = 'archivada' THEN 10
            ELSE 9
        END
        WHERE estado_id IS NULL;
    END IF;
END $$;

UPDATE conversacion SET estado_id = 9 WHERE estado_id IS NULL;
ALTER TABLE conversacion ALTER COLUMN estado_id SET DEFAULT 9;
ALTER TABLE conversacion ALTER COLUMN estado_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'conversacion_estado_id_fkey') THEN
        ALTER TABLE conversacion ADD CONSTRAINT conversacion_estado_id_fkey
            FOREIGN KEY (estado_id) REFERENCES estado(id_estado);
    END IF;
END $$;

-- La columna varchar antigua solo existe en BD frescas -> drop seguro.
ALTER TABLE conversacion DROP COLUMN IF EXISTS estado;
"""


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
-- Trigger 3: Validate INSERT — guard against archived
-- conversations (estado ARCHIVADA=10). Usa estado_id
-- (columna real, ya que conversacion.estado es FK).
-- ============================================
CREATE OR REPLACE FUNCTION validate_mensaje_insert()
RETURNS TRIGGER AS $$
DECLARE
    v_estado       conversacion.estado_id%TYPE;
    v_cliente_id   conversacion.cliente_id%TYPE;
    v_proveedor_id conversacion.proveedor_id%TYPE;
BEGIN
    SELECT estado_id, cliente_id, proveedor_id
    INTO v_estado, v_cliente_id, v_proveedor_id
    FROM conversacion
    WHERE id_conversacion = NEW.conversacion_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'MSG_CONV_NOT_FOUND';
    END IF;

    IF v_estado = 10 THEN  -- ARCHIVADA
        RAISE EXCEPTION 'MSG_IN_ARCHIVED';
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


-- ============================================
-- Trigger 4: Soft-delete — decrement unread_count
-- when an unread message is archived.
-- ============================================
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

SQL_DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS trg_mensaje_conver_meta       ON mensaje;
DROP TRIGGER IF EXISTS trg_mensaje_editado           ON mensaje;
DROP TRIGGER IF EXISTS trg_mensaje_validate          ON mensaje;
DROP TRIGGER IF EXISTS trg_mensaje_softdelete_unread ON mensaje;

DROP FUNCTION IF EXISTS maintain_conversacion_meta();
DROP FUNCTION IF EXISTS mark_mensaje_editado();
DROP FUNCTION IF EXISTS validate_mensaje_insert();
DROP FUNCTION IF EXISTS decrement_unread_on_soft_delete();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("mensajeria", "0001_initial"),
        ("servicios", "0004_tipocambio_estado_oferta_emisor_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="mensaje",
            options={"ordering": ("fecha",)},
        ),
        # estado: varchar -> FK servicios.Estado (default 9 = ACTIVA).
        # Remoto: estado_id ya existe como FK por SQL directo -> no-op.
        # BD fresca: convierte la columna varchar 'estado' a estado_id.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="conversacion",
                    name="estado",
                    field=models.ForeignKey(
                        default=9,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="conversaciones",
                        to="servicios.estado",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=SQL_CONVERT_ESTADO,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
        migrations.AddField(
            model_name="conversacion",
            name="ultimo_mensaje_fecha",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="conversacion",
            name="ultimo_mensaje_preview",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="conversacion",
            name="unread_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="conversacion",
            name="servicio",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="conversaciones",
                to="servicios.servicio",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="conversacion",
            unique_together={("cliente", "proveedor", "servicio")},
        ),
        migrations.AddField(
            model_name="mensaje",
            name="editado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mensaje",
            name="estado_entrega",
            field=models.CharField(
                choices=[
                    ("enviado", "Enviado"),
                    ("recibido", "Recibido"),
                    ("leido", "Leído"),
                ],
                default="enviado",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="mensaje",
            name="tipo_mensaje",
            field=models.CharField(
                choices=[("texto", "Texto"), ("archivo", "Archivo")],
                default="texto",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="mensaje",
            name="archivo",
            field=models.FileField(
                blank=True, null=True, upload_to="mensajes/archivos/"
            ),
        ),
        migrations.AddField(
            model_name="mensaje",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mensaje",
            name="reply_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="respuestas",
                to="mensajeria.mensaje",
            ),
        ),
        migrations.AddIndex(
            model_name="conversacion",
            index=models.Index(
                fields=["cliente", "ultimo_mensaje_fecha"],
                name="conv_cliente_fecha_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="conversacion",
            index=models.Index(
                fields=["proveedor", "ultimo_mensaje_fecha"],
                name="conv_proveedor_fecha_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="mensaje",
            index=models.Index(
                fields=["conversacion", "fecha"],
                name="msg_conversacion_fecha_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="mensaje",
            index=models.Index(fields=["deleted_at"], name="msg_deleted_at_idx"),
        ),
        migrations.RunSQL(
            sql=SQL_CREATE_TRIGGERS,
            reverse_sql=SQL_DROP_TRIGGERS,
            elidable=False,
        ),
    ]
