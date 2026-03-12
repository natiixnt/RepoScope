from app.auth.service import AuthService


def test_login_success() -> None:
    assert AuthService().login("admin", "admin")
