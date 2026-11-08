# referrer_tracker.py の中身
from typing import Optional

def extract_referrer_id(query_params: dict) -> Optional[str]:
    """URLパラメータ等から紹介者ID(?ref=xxx)を抽出"""
    return query_params.get("ref", None)

def register_user_with_referrer(supabase_client, user_id: str, referrer_id: Optional[str] = None):
    """chat_logs_v2_1テーブルにユーザーを登録（すでに存在する場合はスキップ）"""
    try:
        existing = supabase_client.table("chat_logs_v2_1").select("user_id").eq("user_id", user_id).execute()
        if not existing.data:
            supabase_client.table("chat_logs_v2_1").insert({
                "user_id": user_id,
                "referrer_id": referrer_id
            }).execute()
    except Exception as e:
        print(f"User registration error: {e}")
