import uuid

from usuarios.supabase_admin import get_supabase_admin

# Privado (a diferencia de profile_photos) — los adjuntos de chat solo deben
# ser accesibles vía MensajeArchivoView (auth + IsParticipant), nunca por URL
# pública directa.
ARCHIVOS_BUCKET = "mensajeria_archivos"


def _ensure_bucket():
    admin = get_supabase_admin()
    try:
        admin.storage.create_bucket(ARCHIVOS_BUCKET, options={"public": False})
    except Exception:
        pass  # ya existe


def upload_mensaje_archivo(conversacion_id, archivo) -> str:
    """Sube `archivo` (UploadedFile de Django) al bucket privado de
    mensajería y devuelve el storage path (no la URL — el bucket es
    privado, se descarga vía service-role desde MensajeArchivoView)."""
    ext = archivo.name.rsplit(".", 1)[-1] if "." in archivo.name else "bin"
    path = f"conversacion_{conversacion_id}/{uuid.uuid4().hex}.{ext}"

    _ensure_bucket()
    get_supabase_admin().storage.from_(ARCHIVOS_BUCKET).upload(
        path,
        archivo.read(),
        file_options={
            "content-type": archivo.content_type or "application/octet-stream",
        },
    )
    return path


def download_mensaje_archivo(path: str) -> bytes:
    return get_supabase_admin().storage.from_(ARCHIVOS_BUCKET).download(path)
