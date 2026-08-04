# Idempotente: la columna ya existe en la BD remota (creada por SQL directo
# del equipo). En BD frescas la crea; en el remoto es no-op (IF NOT EXISTS).
# El estado de Django registra el campo para que el modelo no genere drift.

from django.db import migrations, models

SQL_ADD = """
ALTER TABLE postulacion
    ADD COLUMN IF NOT EXISTS fecha_actualizacion timestamptz NOT NULL DEFAULT now();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("servicios", "0002_vistainfoaplicantes_vistapostdetails"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="postulacion",
                    name="fecha_actualizacion",
                    field=models.DateTimeField(auto_now_add=True),
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
