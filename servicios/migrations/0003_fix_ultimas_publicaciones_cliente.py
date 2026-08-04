from django.db import migrations

FORWARD_SQL = """
DROP FUNCTION IF EXISTS public.ultimas_publicaciones_cliente(uuid);

CREATE FUNCTION public.ultimas_publicaciones_cliente(p_cliente_id uuid)
 RETURNS TABLE (
    id_servicio integer,
    titulo character varying,
    descripcion text,
    precio_inicial numeric,
    latitud numeric,
    longitud numeric,
    fecha timestamptz,
    imagenes character varying[],
    fecha_final timestamptz,
    categoria_id integer,
    cliente_id uuid,
    tipo_cambio_id integer,
    estado_id integer
 )
 LANGUAGE sql
 STABLE
AS $function$
    SELECT
        id_servicio, titulo, descripcion, precio_inicial, latitud, longitud,
        fecha, imagenes, fecha_final, categoria_id, cliente_id, tipo_cambio_id,
        estado_id
    FROM servicio
    WHERE cliente_id = p_cliente_id
    ORDER BY fecha DESC
    LIMIT 5;
$function$
"""

REVERSE_SQL = """
DROP FUNCTION IF EXISTS public.ultimas_publicaciones_cliente(uuid);

CREATE FUNCTION public.ultimas_publicaciones_cliente(p_cliente_id uuid)
 RETURNS SETOF servicio
 LANGUAGE sql
 STABLE
AS $function$
    SELECT * FROM servicio
    WHERE cliente_id = p_cliente_id
    ORDER BY fecha DESC
    LIMIT 5;
$function$
"""


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0002_vistainfoaplicantes_vistapostdetails'),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
