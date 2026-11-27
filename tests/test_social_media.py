import unittest
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config.database import Base, get_db
from main import app


class SocialMediaApiTestCase(unittest.TestCase):
    """Integration tests for Auth + Social Media endpoints."""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

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

    def _register_and_login(
        self,
        username: str,
        email: str,
        password: str = "securepass123",
        display_name: str | None = None,
    ) -> tuple[dict, dict[str, str]]:
        reg_resp = self.client.post(
            "/auth/register",
            json={
                "username": username,
                "email": email,
                "password": password,
                "display_name": display_name,
            },
        )
        self.assertEqual(reg_resp.status_code, 201, reg_resp.text)
        user = reg_resp.json()
        self.assertNotIn("hashed_password", user)
        self.assertNotIn("password", user)

        login_resp = self.client.post(
            "/auth/login",
            data={"username": user["username"], "password": password},
        )
        self.assertEqual(login_resp.status_code, 200, login_resp.text)
        token = login_resp.json()["access_token"]
        return user, {"Authorization": f"Bearer {token}"}

    def test_register_login_and_profile_authorization(self) -> None:
        alice, alice_headers = self._register_and_login(
            "  alice  ", "alice@example.com", display_name="Alice"
        )
        bob, bob_headers = self._register_and_login("bob", "bob@example.com")
        self.assertEqual(alice["username"], "alice")

        # Login with email also works
        email_login = self.client.post(
            "/auth/login",
            data={"username": "alice@example.com", "password": "securepass123"},
        )
        self.assertEqual(email_login.status_code, 200)

        # Wrong password -> 401
        bad_login = self.client.post(
            "/auth/login",
            data={"username": "alice", "password": "wrongpassword"},
        )
        self.assertEqual(bad_login.status_code, 401)

        # Unauthenticated /auth/me -> 401
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

        # Authenticated /auth/me & /users/me
        me_resp = self.client.get("/auth/me", headers=alice_headers)
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["id"], alice["id"])

        # Duplicate registration -> 409
        dup_resp = self.client.post(
            "/auth/register",
            json={
                "username": "alice",
                "email": "alice2@example.com",
                "password": "securepass123",
            },
        )
        self.assertEqual(dup_resp.status_code, 409)

        # Alice updates her own bio -> 200
        patch_resp = self.client.patch(
            f"/users/{alice['id']}",
            json={"bio": "Hello world!"},
            headers=alice_headers,
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.json()["bio"], "Hello world!")

        # Bob cannot edit or delete Alice -> 403
        forbid_patch = self.client.patch(
            f"/users/{alice['id']}",
            json={"bio": "Hacked"},
            headers=bob_headers,
        )
        self.assertEqual(forbid_patch.status_code, 403)

        forbid_del = self.client.delete(
            f"/users/{alice['id']}",
            headers=bob_headers,
        )
        self.assertEqual(forbid_del.status_code, 403)

        # Explicit null on non-nullable username -> 422
        null_patch = self.client.patch(
            f"/users/{alice['id']}",
            json={"username": None},
            headers=alice_headers,
        )
        self.assertEqual(null_patch.status_code, 422)

    def test_posts_comments_likes_and_ownership(self) -> None:
        alice, alice_headers = self._register_and_login("alice", "alice@example.com")
        bob, bob_headers = self._register_and_login("bob", "bob@example.com")

        # Unauthenticated post creation -> 401
        self.assertEqual(
            self.client.post("/posts/", json={"content": "Nope"}).status_code, 401
        )

        # Alice creates a post
        post_resp = self.client.post(
            "/posts/",
            json={"content": "  First post!  ", "image_url": "https://example.com/pic.png"},
            headers=alice_headers,
        )
        self.assertEqual(post_resp.status_code, 201)
        post = post_resp.json()
        self.assertEqual(post["author_id"], alice["id"])
        self.assertEqual(post["content"], "First post!")

        # Bob cannot edit or delete Alice's post -> 403
        self.assertEqual(
            self.client.patch(
                f"/posts/{post['id']}",
                json={"content": "Hijacked"},
                headers=bob_headers,
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(f"/posts/{post['id']}", headers=bob_headers).status_code,
            403,
        )

        # Alice edits her post -> 200
        patch_post = self.client.patch(
            f"/posts/{post['id']}",
            json={"content": "Updated post!"},
            headers=alice_headers,
        )
        self.assertEqual(patch_post.status_code, 200)
        self.assertEqual(patch_post.json()["content"], "Updated post!")
        self.assertIsNotNone(patch_post.json()["updated_at"])

        # Bob likes and comments
        like_resp = self.client.post(
            f"/posts/{post['id']}/like", headers=bob_headers
        )
        self.assertEqual(like_resp.status_code, 200)
        self.assertTrue(like_resp.json()["liked"])
        self.assertEqual(like_resp.json()["likes_count"], 1)

        # Duplicate like -> 409
        self.assertEqual(
            self.client.post(f"/posts/{post['id']}/like", headers=bob_headers).status_code,
            409,
        )

        comment_resp = self.client.post(
            f"/posts/{post['id']}/comments",
            json={"content": "Nice post!"},
            headers=bob_headers,
        )
        self.assertEqual(comment_resp.status_code, 201)
        comment_id = comment_resp.json()["id"]
        self.assertEqual(comment_resp.json()["author_id"], bob["id"])

        # Alice cannot edit Bob's comment -> 403
        self.assertEqual(
            self.client.patch(
                f"/posts/comments/{comment_id}",
                json={"content": "Hacked comment"},
                headers=alice_headers,
            ).status_code,
            403,
        )

        # Bob updates and deletes his comment -> 200, 204
        edit_comment = self.client.patch(
            f"/posts/comments/{comment_id}",
            json={"content": "Edited comment!"},
            headers=bob_headers,
        )
        self.assertEqual(edit_comment.status_code, 200)
        self.assertEqual(edit_comment.json()["content"], "Edited comment!")

        # Unlike and delete
        unlike_resp = self.client.delete(
            f"/posts/{post['id']}/like", headers=bob_headers
        )
        self.assertEqual(unlike_resp.status_code, 200)
        self.assertEqual(unlike_resp.json()["likes_count"], 0)

        self.assertEqual(
            self.client.delete(
                f"/posts/comments/{comment_id}", headers=bob_headers
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.delete(
                f"/posts/{post['id']}", headers=alice_headers
            ).status_code,
            204,
        )

    def test_follows_and_authenticated_feed(self) -> None:
        alice, alice_headers = self._register_and_login("alice", "alice@example.com")
        bob, bob_headers = self._register_and_login("bob", "bob@example.com")
        carol, carol_headers = self._register_and_login("carol", "carol@example.com")

        # Cannot follow self -> 400
        self.assertEqual(
            self.client.post(
                f"/users/{alice['id']}/follow", headers=alice_headers
            ).status_code,
            400,
        )

        # Alice follows Bob
        follow_resp = self.client.post(
            f"/users/{bob['id']}/follow", headers=alice_headers
        )
        self.assertEqual(follow_resp.status_code, 200)
        self.assertTrue(follow_resp.json()["following"])
        self.assertEqual(follow_resp.json()["followers_count"], 1)

        # Posts by Alice, Bob, and Carol
        self.client.post("/posts/", json={"content": "Alice post"}, headers=alice_headers)
        self.client.post("/posts/", json={"content": "Bob post"}, headers=bob_headers)
        self.client.post("/posts/", json={"content": "Carol post"}, headers=carol_headers)

        # Alice's authenticated feed includes Alice + Bob, not Carol
        feed_resp = self.client.get("/users/me/feed", headers=alice_headers)
        self.assertEqual(feed_resp.status_code, 200)
        contents = [p["content"] for p in feed_resp.json()]
        self.assertIn("Alice post", contents)
        self.assertIn("Bob post", contents)
        self.assertNotIn("Carol post", contents)

        # Unfollow Bob
        unfollow_resp = self.client.delete(
            f"/users/{bob['id']}/follow", headers=alice_headers
        )
        self.assertEqual(unfollow_resp.status_code, 200)
        self.assertFalse(unfollow_resp.json()["following"])
        self.assertEqual(unfollow_resp.json()["followers_count"], 0)

        # Alice deletes her own account -> 204
        self.assertEqual(
            self.client.delete(
                f"/users/{alice['id']}", headers=alice_headers
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.get(f"/users/{alice['id']}").status_code, 404
        )


if __name__ == "__main__":
    unittest.main()
