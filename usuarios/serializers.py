from rest_framework import serializers
from .models import Usuario

ROL_ID_TO_ROLE = {
    1: "client",
    2: "provider",
    3: "admin",
}


class UsuarioSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()
    id_categoria = serializers.IntegerField(source='categoria_id', allow_null=True)
    id_empresa = serializers.IntegerField(source='empresa_id', allow_null=True)

    class Meta:
        model = Usuario
        fields = [
            'id_usuario', 'nombre', 'segundo_nombre', 'apellido_pa',
            'apellido_ma', 'correo', 'celular', 'url_foto_perfil',
            'fecha_registro', 'estado', 'rol', 'id_categoria', 'id_empresa',
        ]

    def get_rol(self, obj):
        return ROL_ID_TO_ROLE.get(obj.rol_id, "client")
