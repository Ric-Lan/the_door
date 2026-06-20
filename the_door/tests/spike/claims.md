# 整合宣稱（從描述語意獨立推出，未參考 edges）

來源規則：只讀每個功能的「名字 + docstring」推「它語意上應該連到什麼」。

| # | 宣稱（from → to） | 推理依據（純語意） | 預期現實 |
|---|---|---|---|
| 1 | UserService.save_user → Database | 「save_user / 持久化使用者」語意上必須落地到儲存 | ❌ 斷裂（已知） |
| 2 | OrderService.create → Database | 「建立訂單」需寫入儲存 | ✅ 有撐 |
| 3 | ReportService.monthly → Database | 「月報表」需讀儲存 | ✅ 有撐 |
| 4 | AuthService.login → Database | 「登入驗證」需查使用者表 | ✅ 有撐 |
| 5 | UserService.save_user → RedisCache（外部、非程式碼節點） | 「快取」常為外部系統、無對應程式碼節點 | ⚠ 無法判定 |

註：宣稱 1 與 5 的「應該要連」純由語意得出，作者寫此表時尚未執行抽取、未看過任何 edge。
