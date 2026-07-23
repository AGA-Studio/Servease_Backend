from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from usuarios.models import Usuario
from usuarios.storage import delete_profile_photos
from usuarios.supabase_admin import get_supabase_admin

CONFIRMATION_WINDOW = timedelta(hours=24)


class Command(BaseCommand):
    help = (
        'Deletes accounts (Usuario row, Supabase auth user, and any '
        'uploaded profile photo) that were never confirmed within 24 hours '
        'of signing up. Intended to run on a schedule (e.g. hourly cron).'
    )

    def handle(self, *args, **options):
        cutoff = timezone.now() - CONFIRMATION_WINDOW
        stale_users = Usuario.objects.filter(estado=False, fecha_registro__lt=cutoff)

        count = 0
        for usuario in stale_users:
            user_id = usuario.id_usuario
            delete_profile_photos(user_id)
            try:
                get_supabase_admin().auth.admin.delete_user(str(user_id))
            except Exception as exc:
                self.stderr.write(
                    f'Could not delete auth user {user_id}: {exc}'
                )
                continue
            usuario.delete()
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Deleted {count} unconfirmed account(s).'))
