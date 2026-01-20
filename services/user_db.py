"""
ユーザー管理DB（Google Sheets版）
無料枠のカウント管理
Render free tier (ephemeral storage) 対策のためスプレッドシートを使用
"""
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from typing import Optional
from config import settings

class UserDB:
    def __init__(self):
        self.sheet_id = settings.GOOGLE_SHEETS_ID
        self.creds_path = settings.GOOGLE_SERVICE_ACCOUNT_KEY
        
        # スコープ設定
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        try:
            # 認証
            self.creds = ServiceAccountCredentials.from_json_keyfile_name(self.creds_path, scope)
            self.client = gspread.authorize(self.creds)
            
            # スプレッドシートを開く
            self.sheet = self.client.open_by_key(self.sheet_id)
            print(f"Connected to Google Sheet: {self.sheet.title}", flush=True)
            
            # ワークシート初期化
            self._init_worksheets()
            
        except Exception as e:
            print(f"Google Sheets connection error: {e}", flush=True)
            raise e

    def _init_worksheets(self):
        """ワークシートの取得または作成"""
        # Usersシート
        try:
            self.users_ws = self.sheet.worksheet("Users")
        except gspread.WorksheetNotFound:
            self.users_ws = self.sheet.add_worksheet(title="Users", rows=1000, cols=4)
            self.users_ws.append_row(["user_id", "created_at", "is_premium", "premium_expires_at"])
            
        # Usageシート
        try:
            self.usage_ws = self.sheet.worksheet("Usage")
        except gspread.WorksheetNotFound:
            self.usage_ws = self.sheet.add_worksheet(title="Usage", rows=1000, cols=3)
            self.usage_ws.append_row(["user_id", "used_at", "month"])

    def create_user(self, user_id: str) -> bool:
        """ユーザー作成（存在しなければ）"""
        try:
            # 既存チェック
            cell = self.users_ws.find(user_id)
            if cell:
                return True
                
            # 新規作成
            self.users_ws.append_row([
                user_id,
                datetime.now().isoformat(),
                0, # is_premium (False)
                "" # premium_expires_at
            ])
            return True
        except Exception as e:
            print(f"Create user error: {e}")
            return False

    def get_user(self, user_id: str) -> Optional[dict]:
        """ユーザー情報取得"""
        try:
            cell = self.users_ws.find(user_id)
            if not cell:
                return None
                
            row_values = self.users_ws.row_values(cell.row)
            
            # データ整形
            # [user_id, created_at, is_premium, premium_expires_at]
            is_premium = False
            if len(row_values) > 2:
                val = row_values[2]
                is_premium = str(val).lower() in ('true', '1', 'on')
                
            premium_expires_at = None
            if len(row_values) > 3:
                premium_expires_at = row_values[3]
                
            return {
                "user_id": row_values[0],
                "created_at": row_values[1] if len(row_values) > 1 else "",
                "is_premium": is_premium,
                "premium_expires_at": premium_expires_at
            }
        except Exception as e:
            print(f"Get user error: {e}")
            return None

    def get_monthly_usage(self, user_id: str) -> int:
        """今月の使用回数を取得"""
        try:
            current_month = datetime.now().strftime("%Y-%m")
            
            # 全データを取得してPython側でフィルタリング（データ量増えると遅くなるが、今回は簡易実装）
            # 最適化するなら query 機能を使うか、月別シートにする
            records = self.usage_ws.get_all_records()
            
            count = 0
            for record in records:
                # gspreadのget_all_recordsはヘッダーをキーにする
                if str(record.get("user_id")) == user_id and str(record.get("month")) == current_month:
                    count += 1
                    
            return count
        except Exception as e:
            print(f"Get monthly usage error: {e}")
            return 0 # エラー時は0を返して動作を止めない（またはログ出す）

    def get_remaining_count(self, user_id: str) -> int:
        """残り回数を取得"""
        user = self.get_user(user_id)
        if not user:
            self.create_user(user_id)
            user = self.get_user(user_id)
            
        used = self.get_monthly_usage(user_id)
        
        # プレミアムユーザーは月15回
        if user and user["is_premium"]:
            if user["premium_expires_at"]:
                try:
                    expires = datetime.fromisoformat(user["premium_expires_at"])
                    if expires > datetime.now():
                        remaining = settings.PREMIUM_MONTHLY_LIMIT - used
                        return max(0, remaining)
                except ValueError:
                    pass # 日付フォーマットエラーなどは無視して無料枠へ
                    
        # 無料ユーザーは月3回
        remaining = settings.FREE_MONTHLY_LIMIT - used
        return max(0, remaining)

    def increment_usage(self, user_id: str) -> bool:
        """使用回数をインクリメント"""
        try:
            current_month = datetime.now().strftime("%Y-%m")
            self.usage_ws.append_row([
                user_id,
                datetime.now().isoformat(),
                current_month
            ])
            return True
        except Exception as e:
            print(f"Increment usage error: {e}")
            return False

    def set_premium(self, user_id: str, expires_at: datetime) -> bool:
        """プレミアム設定"""
        try:
            cell = self.users_ws.find(user_id)
            if not cell:
                self.create_user(user_id)
                cell = self.users_ws.find(user_id)
                
            # is_premium (col 3), expires_at (col 4) を更新
            self.users_ws.update_cell(cell.row, 3, 1) # 1 = True
            self.users_ws.update_cell(cell.row, 4, expires_at.isoformat())
            return True
        except Exception as e:
            print(f"Set premium error: {e}")
            return False

    def cancel_premium(self, user_id: str) -> bool:
        """プレミアム解除"""
        try:
            cell = self.users_ws.find(user_id)
            if cell:
                # is_premium -> 0, expires -> ""
                self.users_ws.update_cell(cell.row, 3, 0)
                self.users_ws.update_cell(cell.row, 4, "")
            return True
        except Exception as e:
            print(f"Cancel premium error: {e}")
            return False
