# referrer_tracker.py
from typing import Optional

def extract_referrer_id(query_params: dict) -> Optional[str]:
    """
    URLクエリパラメータ等から紹介者ID(?ref=xxx)を抽出
    """
    return query_params.get("ref", None)

def build_share_link(user_id: str, base_url: str = "https://your-ikkyu-app.com") -> str:
    """
    ユーザー専用の紹介用リンクを生成
    """
    return f"{base_url}?ref={user_id}"
