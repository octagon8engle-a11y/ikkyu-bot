# referrer_tracker.py の中身
from typing import Optional

def extract_referrer_id(query_params: dict) -> Optional[str]:
    """URLパラメータ等から紹介者ID(?ref=xxx)を抽出"""
    return query_params.get("ref", None)

def register_user_with_referrer(supabase_client, user_id: str, referrer_id: Optional[str] = None):
    """users_v1_2テーブルにユーザーを登録（すでに存在する場合はスキップ）"""
    try:
        existing = supabase_client.table("users_v1_2").select("user_id").eq("user_id", user_id).execute()
        if not existing.data:
            supabase_client.table("users_v1_2").insert({
                "user_id": user_id,
                "referrer_id": referrer_id
            }).execute()
    except Exception as e:
        print(f"User registration error: {e}")
