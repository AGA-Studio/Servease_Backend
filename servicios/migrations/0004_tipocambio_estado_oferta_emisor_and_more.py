# Idempotente: tablas/columnas ya existen en la BD remota (SQL directo del
# equipo). En BD frescas las crea; en el remoto son no-op (IF NOT EXISTS).
# El state registra los modelos/campos para que Django no genere drift.
# Los nombres de constraint coinciden con los del remoto para que el
# DO block los detecte y no intente recrearlos.

import django.db.models.deletion
from django.db import migrations, models


# Catálogo de estados (constantes en servicios/models/estado.py).
# get_or_create: inserta solo los IDs faltantes; no toca filas existentes.
ESTADOS = [
    (1, "ACEPTADO"),
    (2, "PENDIENTE"),
    (3, "RECHAZADA"),
    (4, "PROGRESO"),
    (5, "COMPLETADO"),
    (6, "CONTRAOFERTA"),
    (7, "ABIERTO"),
    (8, "CANCELADO"),
    (9, "ACTIVA"),      # mensajería
    (10, "ARCHIVADA"),  # mensajería
]


def seed_estados(apps, schema_editor):
    Estado = apps.get_model("servicios", "Estado")
    for id_estado, descripcion in ESTADOS:
        Estado.objects.get_or_create(id_estado=id_estado, defaults={"descripcion": descripcion})


def unseed_estados(apps, schema_editor):
    Estado = apps.get_model("servicios", "Estado")
    Estado.objects.filter(id_estado__in=[9, 10]).delete()


SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS estado (
    id_estado serial PRIMARY KEY,
    descripcion varchar(50) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS tipo_cambio (
    id_tipo_cambio serial PRIMARY KEY,
    nombre varchar(10) NOT NULL
);
ALTER TABLE oferta      ADD COLUMN IF NOT EXISTS emisor_id uuid;
ALTER TABLE oferta      ADD COLUMN IF NOT EXISTS estado_id integer;
ALTER TABLE postulacion ADD COLUMN IF NOT EXISTS estado_id integer;
ALTER TABLE servicio    ADD COLUMN IF NOT EXISTS estado_id integer;
ALTER TABLE servicio    ADD COLUMN IF NOT EXISTS tipo_cambio_id integer;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'oferta_emisor_id_fkey') THEN
        ALTER TABLE oferta ADD CONSTRAINT oferta_emisor_id_fkey
            FOREIGN KEY (emisor_id) REFERENCES usuario(id_usuario);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'oferta_estado_id_fkey') THEN
        ALTER TABLE oferta ADD CONSTRAINT oferta_estado_id_fkey
            FOREIGN KEY (estado_id) REFERENCES estado(id_estado);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_postulacion_estado') THEN
        ALTER TABLE postulacion ADD CONSTRAINT fk_postulacion_estado
            FOREIGN KEY (estado_id) REFERENCES estado(id_estado);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_servicio_estado') THEN
        ALTER TABLE servicio ADD CONSTRAINT fk_servicio_estado
            FOREIGN KEY (estado_id) REFERENCES estado(id_estado);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'servicio_tipo_cambio_id_fkey') THEN
        ALTER TABLE servicio ADD CONSTRAINT servicio_tipo_cambio_id_fkey
            FOREIGN KEY (tipo_cambio_id) REFERENCES tipo_cambio(id_tipo_cambio) ON DELETE SET NULL;
    END IF;
END
$$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0003_postulacion_fecha_actualizacion'),
        # FK oferta.emisor -> usuarios.usuario existe desde usuarios 0001;
        # NO arrastrar usuarios 0004 (otra feature, no aplicada en remoto).
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='TipoCambio',
                    fields=[
                        ('id_tipo_cambio', models.AutoField(primary_key=True, serialize=False)),
                        ('nombre', models.CharField(max_length=10)),
                    ],
                    options={
                        'db_table': 'tipo_cambio',
                        'managed': False,
                    },
                ),
                migrations.CreateModel(
                    name='Estado',
                    fields=[
                        ('id_estado', models.AutoField(primary_key=True, serialize=False)),
                        ('descripcion', models.CharField(max_length=50)),
                    ],
                    options={
                        'db_table': 'estado',
                    },
                ),
                migrations.AddField(
                    model_name='oferta',
                    name='emisor',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ofertas_enviadas', to='usuarios.usuario'),
                ),
                migrations.AlterField(
                    model_name='postulacion',
                    name='fecha_actualizacion',
                    field=models.DateTimeField(auto_now_add=True),
                ),
                migrations.AddField(
                    model_name='servicio',
                    name='tipo_cambio',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='servicios', to='servicios.tipocambio'),
                ),
                migrations.AlterField(
                    model_name='oferta',
                    name='estado',
                    field=models.ForeignKey(db_column='estado_id', on_delete=django.db.models.deletion.PROTECT, related_name='ofertas', to='servicios.estado'),
                ),
                migrations.AlterField(
                    model_name='postulacion',
                    name='estado',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='postulaciones', to='servicios.estado'),
                ),
                migrations.AlterField(
                    model_name='servicio',
                    name='estado',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='servicios', to='servicios.estado'),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=SQL_SCHEMA,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
        migrations.RunPython(seed_estados, unseed_estados),
    ]
