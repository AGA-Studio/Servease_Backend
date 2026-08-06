"""Publicación de eventos en tiempo real vía Supabase Realtime.

Reemplaza Django Channels + Redis como capa de mensajería en vivo.
Los clientes (frontend) se suscriben al canal `conversacion-<id>` y el
backend publica eventos tras persistir en PostgreSQL.

Eventos publicados: new_message, typing_start, typing_stop, read_receipt.

Best-effort: si Supabase Realtime no está disponible, la mensajería REST
sigue funcionando; los eventos en vivo simplemente no se entregan.
"""

import asyncio
import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)


async def _broadcast_async(channel_name: str, event: str, payload: dict) -> None:
    """Crea un cliente, publica el broadcast y libera el canal."""
    from supabase import create_async_client

    client = await create_async_client(
        settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
    )
    channel = client.channel(channel_name, {"config": {"private": True}})
    try:
        await channel.subscribe()
        await channel.send_broadcast(event=event, data=payload)
    finally:
        await client.remove_channel(channel)


def publish_event(conversacion_id: int, event: str, payload: dict) -> None:
    """Publica un evento en el canal de la conversación (fire-and-forget).

    Corre en un hilo daemon para no bloquear la respuesta HTTP. Los fallos
    se registran y se ignoran: la mensajería nunca debe romperse por Realtime.
    """

    def runner() -> None:
        try:
            asyncio.run(
                _broadcast_async(f"conversacion-{conversacion_id}", event, payload)
            )
        except Exception:
            logger.warning(
                "Realtime broadcast falló: conv=%s event=%s", conversacion_id, event,
                exc_info=True,
            )

    threading.Thread(target=runner, daemon=True).start()
