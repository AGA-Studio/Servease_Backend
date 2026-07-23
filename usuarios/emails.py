import httpx
from django.conf import settings
from django.template.loader import render_to_string


def send_confirmation_email(to_email: str, confirm_url: str) -> None:
    html = render_to_string('emails/confirm_account.html', {'confirm_url': confirm_url})

    response = httpx.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
        json={
            'from': settings.RESEND_FROM_EMAIL,
            'to': [to_email],
            'subject': 'Confirma tu cuenta de Servease',
            'html': html,
        },
        timeout=10,
    )
    response.raise_for_status()
