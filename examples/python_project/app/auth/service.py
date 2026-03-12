from app.db.client import DBClient


class AuthService:
    def __init__(self) -> None:
        self.db = DBClient()

    def login(self, username: str, password: str) -> bool:
        return username == "admin" and password == "admin"
