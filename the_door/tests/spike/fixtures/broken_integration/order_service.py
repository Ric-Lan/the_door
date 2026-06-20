"""訂單服務：正確把資料寫進 Database。"""
from db import Database


class OrderService:
    def __init__(self):
        self.db = Database()

    def create(self, order):
        self.db.connect()
        return self.db.query("INSERT INTO orders ...")
