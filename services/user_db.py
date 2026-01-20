"""
ユーザー管理DB（SQLite）
無料枠のカウント管理
"""
import os
import sqlite3
from datetime import datetime
from typing import Optional
from config import settings


class UserDB:
    def __init__(self, db_path: str = None):
        # Renderの永続化ディレクトリを優先、なければカレントディレクトリ
        if db_path is None:
            if os.path.exists("/data"):
                db_path = "/data/users.db"
            else:
                db_path = "users.db"

        self.db_path = db_path
        print(f"UserDB initialized with path: {self.db_path}", flush=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """テーブル初期化"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    is_premium INTEGER DEFAULT 0,
                    premium_expires_at TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    used_at TEXT,
                    month TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_user_month
                ON usage(user_id, month)
            """)

            conn.commit()
            conn.close()
            print(f"Database initialized successfully at {self.db_path}", flush=True)
        except Exception as e:
            print(f"Database initialization error: {e}", flush=True)
            raise

    def create_user(self, user_id: str) -> bool:
        """ユーザー作成"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, created_at)
                VALUES (?, ?)
            """, (user_id, datetime.now().isoformat()))
            conn.commit()
            return True
        except Exception as e:
            print(f"Create user error: {e}")
            return False
        finally:
            conn.close()

    def get_user(self, user_id: str) -> Optional[dict]:
        """ユーザー情報取得"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, created_at, is_premium, premium_expires_at
            FROM users WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "user_id": row[0],
                "created_at": row[1],
                "is_premium": bool(row[2]),
                "premium_expires_at": row[3]
            }
        return None

    def get_monthly_usage(self, user_id: str) -> int:
        """今月の使用回数を取得"""
        conn = self._get_connection()
        cursor = conn.cursor()

        current_month = datetime.now().strftime("%Y-%m")

        cursor.execute("""
            SELECT COUNT(*) FROM usage
            WHERE user_id = ? AND month = ?
        """, (user_id, current_month))

        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_remaining_count(self, user_id: str) -> int:
        """残り回数を取得"""
        # ユーザーがいなければ作成
        user = self.get_user(user_id)
        if not user:
            self.create_user(user_id)
            user = self.get_user(user_id)

        # プレミアムユーザーは無制限
        if user and user["is_premium"]:
            # 有効期限チェック
            if user["premium_expires_at"]:
                expires = datetime.fromisoformat(user["premium_expires_at"])
                if expires > datetime.now():
                    return 999  # 無制限を表す

        # 無料ユーザー
        used = self.get_monthly_usage(user_id)
        remaining = settings.FREE_MONTHLY_LIMIT - used
        return max(0, remaining)

    def increment_usage(self, user_id: str) -> bool:
        """使用回数をインクリメント"""
        conn = self._get_connection()
        cursor = conn.cursor()

        current_month = datetime.now().strftime("%Y-%m")

        try:
            cursor.execute("""
                INSERT INTO usage (user_id, used_at, month)
                VALUES (?, ?, ?)
            """, (user_id, datetime.now().isoformat(), current_month))
            conn.commit()
            return True
        except Exception as e:
            print(f"Increment usage error: {e}")
            return False
        finally:
            conn.close()

    def set_premium(self, user_id: str, expires_at: datetime) -> bool:
        """プレミアム設定"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users SET is_premium = 1, premium_expires_at = ?
                WHERE user_id = ?
            """, (expires_at.isoformat(), user_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Set premium error: {e}")
            return False
        finally:
            conn.close()

    def cancel_premium(self, user_id: str) -> bool:
        """プレミアム解除"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users SET is_premium = 0, premium_expires_at = NULL
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Cancel premium error: {e}")
            return False
        finally:
            conn.close()
