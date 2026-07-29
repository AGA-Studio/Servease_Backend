from rest_framework import serializers

from .models import VistaDashboardProveedor, VistaPostDetails, VistaTrabajosDisponibles


class DashboardProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaDashboardProveedor
        fields = '__all__'


class DashboardPostDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaPostDetails
        fields = '__all__'


class DashboardTrabajosDisponiblesSerializer(serializers.ModelSerializer):
    class Meta:
        model = VistaTrabajosDisponibles
        fields = '__all__'
