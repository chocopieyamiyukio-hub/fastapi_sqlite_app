import unittest
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config.database import Base, get_db
from main import app


class ItemApiTestCase(unittest.TestCase):
    """Integration tests for Item CRUD endpoints and Pydantic validation."""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        Base.metadata.create_all(bind=self.engine)

        def override_get_db() -> Generator[Session, None, None]:
            db = self.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_health_check(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.json())

    def test_create_and_read_item_strips_whitespace(self) -> None:
        response = self.client.post(
            "/items/",
            json={
                "name": "  Laptop  ",
                "description": "  Gaming laptop  ",
                "price": 1200.5,
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["name"], "Laptop")
        self.assertEqual(data["description"], "Gaming laptop")
        self.assertEqual(data["price"], 1200.5)
        self.assertTrue(data["is_active"])

        list_resp = self.client.get("/items/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()), 1)

        get_resp = self.client.get("/items/1")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["name"], "Laptop")

    def test_validation_rejects_extra_fields_blank_name_and_negative_price(self) -> None:
        extra_resp = self.client.post(
            "/items/",
            json={"name": "Book", "price": 10.0, "unknown": "bad"},
        )
        self.assertEqual(extra_resp.status_code, 422)

        blank_resp = self.client.post(
            "/items/",
            json={"name": "   ", "price": 10.0},
        )
        self.assertEqual(blank_resp.status_code, 422)

        neg_price_resp = self.client.post(
            "/items/",
            json={"name": "Book", "price": -5.0},
        )
        self.assertEqual(neg_price_resp.status_code, 422)

    def test_patch_and_put_and_delete(self) -> None:
        created = self.client.post(
            "/items/",
            json={"name": "Mouse", "description": "Wireless", "price": 25.0},
        ).json()
        item_id = created["id"]

        # Partial update via PATCH
        patch_resp = self.client.patch(
            f"/items/{item_id}",
            json={"price": 30.0},
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.json()["name"], "Mouse")
        self.assertEqual(patch_resp.json()["price"], 30.0)

        # Reject explicit null on non-nullable column
        null_patch = self.client.patch(
            f"/items/{item_id}",
            json={"name": None},
        )
        self.assertEqual(null_patch.status_code, 422)

        # Allow clearing nullable description
        clear_desc = self.client.patch(
            f"/items/{item_id}",
            json={"description": None},
        )
        self.assertEqual(clear_desc.status_code, 200)
        self.assertIsNone(clear_desc.json()["description"])

        # Full replace via PUT
        put_resp = self.client.put(
            f"/items/{item_id}",
            json={"name": "Keyboard", "price": 50.0},
        )
        self.assertEqual(put_resp.status_code, 200)
        self.assertEqual(put_resp.json()["name"], "Keyboard")
        self.assertIsNone(put_resp.json()["description"])
        self.assertTrue(put_resp.json()["is_active"])

        # Delete returns 204 No Content
        del_resp = self.client.delete(f"/items/{item_id}")
        self.assertEqual(del_resp.status_code, 204)
        self.assertEqual(del_resp.content, b"")

        # Subsequent GET returns 404
        missing_resp = self.client.get(f"/items/{item_id}")
        self.assertEqual(missing_resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
