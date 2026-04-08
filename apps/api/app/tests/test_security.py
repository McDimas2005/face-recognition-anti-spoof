from app.core.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_round_trip():
    hashed = hash_password("SecretPass123!")
    assert hashed != "SecretPass123!"
    assert verify_password("SecretPass123!", hashed) is True


def test_create_and_decode_token():
    token = create_token("user-1", 5, "access", extra={"role": "admin"})
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"
    assert payload["role"] == "admin"

