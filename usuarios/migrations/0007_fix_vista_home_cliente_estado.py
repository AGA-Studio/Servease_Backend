from django.db import migrations

# `vista_home_cliente.estado` leía `servicio.estado` — una columna de texto
# legada que quedó desincronizada de `servicio.estado_id` (la fuente de
# verdad actual): filas nuevas la traen NULL y filas viejas se quedaron
# congeladas en el valor que tenían antes de que existiera `estado_id`
# (ej. servicio 57: estado='completado' pero estado_id=4 'progreso'). Eso
# hacía que "Mis Publicaciones Activas" en Home mostrara mal los estados
# (o los perdiera del filtro). Se reemplaza por `estado.descripcion` vía
# join con `estado_id`, igual que ya hacen las demás vistas
# (vista_info_aplicantes, vista_post_details).

FORWARD_SQL = """
CREATE OR REPLACE VIEW vista_home_cliente AS
 SELECT s.id_servicio,
    s.titulo,
    s.descripcion,
    cat.nombre AS categoria,
    s.latitud,
    s.longitud,
    s.fecha,
    now() - s.fecha AS tiempo_transcurrido,
    e.descripcion AS estado,
    s.cliente_id,
    COALESCE(aplicantes.fotos, ARRAY[]::character varying[]::text[]) AS fotos_proveedores_aplicantes
   FROM servicio s
     JOIN categoria cat ON cat.id_categoria = s.categoria_id
     JOIN estado e ON e.id_estado = s.estado_id
     LEFT JOIN LATERAL ( SELECT array_agg(DISTINCT u.url_foto_perfil) AS fotos
           FROM postulacion p
             JOIN usuario u ON u.id_usuario = p.proveedor_id
          WHERE p.servicio_id = s.id_servicio AND u.url_foto_perfil IS NOT NULL) aplicantes ON true;
"""

REVERSE_SQL = """
CREATE OR REPLACE VIEW vista_home_cliente AS
 SELECT s.id_servicio,
    s.titulo,
    s.descripcion,
    cat.nombre AS categoria,
    s.latitud,
    s.longitud,
    s.fecha,
    now() - s.fecha AS tiempo_transcurrido,
    s.estado,
    s.cliente_id,
    COALESCE(aplicantes.fotos, ARRAY[]::character varying[]::text[]) AS fotos_proveedores_aplicantes
   FROM servicio s
     JOIN categoria cat ON cat.id_categoria = s.categoria_id
     LEFT JOIN LATERAL ( SELECT array_agg(DISTINCT u.url_foto_perfil) AS fotos
           FROM postulacion p
             JOIN usuario u ON u.id_usuario = p.proveedor_id
          WHERE p.servicio_id = s.id_servicio AND u.url_foto_perfil IS NOT NULL) aplicantes ON true;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0006_split_ganancias_por_moneda'),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
