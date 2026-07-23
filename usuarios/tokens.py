from django.core import signing

CONFIRMATION_SALT = 'usuarios.email-confirmation'
CONFIRMATION_MAX_AGE = 60 * 60 * 24  # 24 hours


def make_confirmation_token(user_id) -> str:
    return signing.dumps({'id': str(user_id)}, salt=CONFIRMATION_SALT)


def verify_confirmation_token(token: str) -> str:
    """Returns the user id encoded in the token.

    Raises signing.SignatureExpired if older than CONFIRMATION_MAX_AGE,
    or signing.BadSignature if the token was tampered with / malformed.
    """
    data = signing.loads(token, salt=CONFIRMATION_SALT, max_age=CONFIRMATION_MAX_AGE)
    return data['id']
