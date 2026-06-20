"""使用者服務：描述上「持久化使用者」，但實作只存在記憶體 —— 故意斷裂。
完全不 import / 不呼叫 Database。"""


class UserService:
    def __init__(self):
        self._users = []

    def save_user(self, user):
        # BUG（故意）：宣稱寫入資料庫，實際只 append 到記憶體 list
        self._users.append(user)
        return True
