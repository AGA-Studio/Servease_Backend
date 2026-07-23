from django.conf import settings
from .supabase_admin import get_supabase_admin

PROFILE_PHOTOS_BUCKET = 'profile_photos'


def upload_profile_photo(user_id, photo) -> str:
    """Uploads `photo` (a Django UploadedFile) to the user's own folder in
    the profile_photos bucket and returns its public URL."""
    ext = (photo.name.rsplit('.', 1)[-1] if '.' in photo.name else 'jpg').lower()
    path = f'user_{user_id}/avatar.{ext}'

    get_supabase_admin().storage.from_(PROFILE_PHOTOS_BUCKET).upload(
        path,
        photo.read(),
        file_options={
            'content-type': photo.content_type or 'image/jpeg',
            'upsert': 'true',
        },
    )

    return (
        f'{settings.SUPABASE_URL}/storage/v1/object/public/'
        f'{PROFILE_PHOTOS_BUCKET}/{path}'
    )


def delete_profile_photos(user_id) -> None:
    """Best-effort delete of every file under the user's folder."""
    bucket = get_supabase_admin().storage.from_(PROFILE_PHOTOS_BUCKET)
    try:
        entries = bucket.list(f'user_{user_id}')
        paths = [f'user_{user_id}/{entry["name"]}' for entry in entries]
        if paths:
            bucket.remove(paths)
    except Exception:
        pass
