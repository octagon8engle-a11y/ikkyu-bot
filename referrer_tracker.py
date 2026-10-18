# 最低限の referrer_tracker.py（これで十分機能します）
from typing import Optional

def extract_referrer_id(text_or_params: str) -> Optional[str]:
    """
    メッセージ本文やパラメータから紹介者ID(?ref=xxx や ref_xxx)を抽出
    """
    if "ref=" in text_or_params:
        return text_or_params.split("ref=")[-1].strip()
    return None

def build_share_link(user_id: str, base_url: str = "https://line.me/R/oaMessage/@your_bot_id/") -> str:
    """
    ユーザー専用の紹介用リンクを生成
    """
    return f"{base_url}?ref={user_id}"
