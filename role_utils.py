from supabase import Client

def get_user_role(supabase: Client, user_id: str) -> str:
    """データベースからユーザーのロールを取得する（未登録なら 'visitor'）"""
    try:
        user_resp = supabase.table("users").select("role").eq("user_id", user_id).execute()
        if user_resp.data:
            return user_resp.data[0].get("role", "visitor")
    except Exception as e:
        print(f"Role fetch error: {e}")
    return "F"
