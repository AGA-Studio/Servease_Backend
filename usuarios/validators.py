import re

from django.utils import timezone
from rest_framework import serializers

# Letras (incl. acentos/ñ), espacios, apóstrofes y guiones — cubre nombres
# compuestos ("María José") y apellidos con guion ("Pérez-López") sin abrir
# la puerta a dígitos o símbolos. Espejo de NAME_PATTERN en
# src/utils/validation.ts (frontend) — el backend es la última línea de
# defensa si alguien llama al API directo, saltándose el formulario.
NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:[\s'-]+[^\W\d_]+)*$", re.UNICODE)
PHONE_DIGITS_PATTERN = re.compile(r"^\d{10}$")


def validate_name(value):
    if not NAME_PATTERN.match(value.strip()):
        raise serializers.ValidationError(
            'Solo se permiten letras, espacios, apóstrofes y guiones.'
        )
    return value


def validate_phone(value):
    if not value:
        return value
    digits = re.sub(r"[\s\-().]", "", value)
    if not PHONE_DIGITS_PATTERN.match(digits):
        raise serializers.ValidationError(
            'Ingresa un número de teléfono válido de 10 dígitos.'
        )
    return value


def validate_birthdate(value):
    if value > timezone.now().date():
        raise serializers.ValidationError(
            'La fecha de nacimiento no puede ser en el futuro.'
        )
    return value
