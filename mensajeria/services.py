from mensajeria.models import Conversacion
from servicios.models.estado import ARCHIVADA


def archivar_conversaciones_de_servicio(servicio_id):
    """Al completarse un servicio, su(s) conversación(es) pasan a solo
    lectura (archivada) — ya no hace falta seguir chateando y evita que se
    sigan mandando ubicaciones/archivos/mensajes sobre un trabajo cerrado."""
    Conversacion.objects.filter(servicio_id=servicio_id).update(
        estado_id=ARCHIVADA
    )
