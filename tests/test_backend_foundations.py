import unittest
import uuid
from datetime import datetime, timezone
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.models import User, Diagram, ExportJob
from app.schemas import UserRegister, UserResponse, DiagramCreate, ExportJobCreate

class TestBackendFoundations(unittest.TestCase):
    def test_settings_defaults(self):
        """Test configuration class settings and their default values."""
        settings = Settings()
        self.assertEqual(settings.MINIO_ACCESS_KEY, "minioadmin")
        self.assertEqual(settings.MINIO_SECRET_KEY, "minioadmin")
        self.assertEqual(settings.JWT_ALGORITHM, "HS256")
        self.assertEqual(settings.ACCESS_TOKEN_EXPIRE_MINUTES, 1440)

    def test_password_hashing(self):
        """Test password hashing and verification logic using bcrypt."""
        password = "secret_password"
        hashed = hash_password(password)
        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrong_password", hashed))

    def test_jwt_token(self):
        """Test JWT token creation, encoding, decoding, and failure handling."""
        data = {"user_id": str(uuid.uuid4()), "role": "user"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["user_id"], data["user_id"])
        self.assertEqual(decoded["role"], "user")
        
        # Test invalid token
        self.assertIsNone(decode_access_token("invalid.token.here"))

    def test_models_instantiation(self):
        """Test that SQLAlchemy models instantiate correctly with properties."""
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="test@example.com",
            hashed_password="hashed_str",
            is_active=True
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.is_active)
        
        diagram = Diagram(
            id=uuid.uuid4(),
            title="My Architecture",
            spec={"elements": []},
            user_id=user_id
        )
        self.assertEqual(diagram.title, "My Architecture")
        self.assertEqual(diagram.spec, {"elements": []})

    def test_schemas_validation(self):
        """Test Pydantic schema validation success and failure cases."""
        # Test valid registration
        reg = UserRegister(email="test@example.com", password="password123")
        self.assertEqual(reg.email, "test@example.com")

        # Test invalid field types
        with self.assertRaises(ValidationError):
            # spec must be a dictionary, passing a string should raise ValidationError
            DiagramCreate(title="Test", spec="not-a-dict")
