# Nuevo campo para el flujo de pago rediseñado: el proveedor marca el
# trabajo como fisicamente terminado, y solo entonces el cliente puede
# elegir metodo de pago (antes el proveedor elegia el metodo directamente
# al completar). No toca `estado`.

from django.db import migrations, models

SQL_ADD = """
ALTER TABLE servicio
    ADD COLUMN IF NOT EXISTS trabajo_terminado boolean NOT NULL DEFAULT false;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("servicios", "0009_fix_conversacion_estado_trigger"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="servicio",
                    name="trabajo_terminado",
                    field=models.BooleanField(default=False),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=SQL_ADD,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
