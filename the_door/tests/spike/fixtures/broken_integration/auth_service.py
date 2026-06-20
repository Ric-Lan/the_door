"""認證服務：正確查 Database 驗證使用者。"""
from db import Database


class AuthService:
    def __init__(self):
        self.db = Database()

    def login(self, name, pw):
        self.db.connect()
        rows = self.db.query("SELECT * FROM users WHERE ...")
        return bool(rows)
