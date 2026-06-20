"""報表服務：正確從 Database 讀資料。"""
from db import Database


class ReportService:
    def __init__(self):
        self.db = Database()

    def monthly(self):
        self.db.connect()
        return self.db.query("SELECT * FROM orders ...")
