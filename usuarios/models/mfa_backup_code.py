# usuarios/models/mfa_backup_code.py
from django.db import models
from .usuario import Usuario


class MfaBackupCode(models.Model):
    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE,
        db_column='id_usuario', related_name='mfa_backup_codes',
    )
    code_hash = models.CharField(max_length=64)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mfa_backup_code'
        indexes = [
            models.Index(fields=['usuario', 'code_hash']),
        ]

    def __str__(self):
        return f"backup code for {self.usuario_id} ({'usado' if self.used_at else 'activo'})"
