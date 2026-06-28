import unittest
from datetime import timedelta
import jwt
from app.utilities.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestSecurityUtilities(unittest.TestCase):

    def test_password_hashing(self):
        password = "SecurePassword123"
        hashed = hash_password(password)

        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrong_password", hashed))

    def test_jwt_token_flow(self):
        payload = {"email": "test@enterprise.com", "role": "Administrator"}

        # Access Token check
        access_token = create_access_token(payload, expires_delta=timedelta(minutes=5))
        decoded = decode_token(access_token)

        self.assertEqual(decoded.get("email"), "test@enterprise.com")
        self.assertEqual(decoded.get("role"), "Administrator")
        self.assertEqual(decoded.get("type"), "access")
        self.assertTrue("exp" in decoded)

        # Refresh Token check
        refresh_token = create_refresh_token(payload, expires_delta=timedelta(minutes=10))
        decoded_refresh = decode_token(refresh_token)

        self.assertEqual(decoded_refresh.get("email"), "test@enterprise.com")
        self.assertEqual(decoded_refresh.get("type"), "refresh")


if __name__ == "__main__":
    unittest.main()
