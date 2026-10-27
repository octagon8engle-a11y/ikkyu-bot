from supabase import Client

def check_usage_limit(supabase: Client, user_id: str, role: str) -> bool:
    """
    admin は無制限、それ以外は chat_logs_v1_1 を参照して回数制限（例: 5回まで）を判定する。
    許可される場合は True、制限に達している場合は False を返す。
    """
    if role == "admin":
        return True
    
    try:
        count_resp = supabase.table("chat_logs_v1_1").select("id", count="exact").eq("user_id", user_id).execute()
        total_count = count_resp.count or 0
        
        if total_count >= 5:
            return False
    except Exception as e:
        print(f"Limit check error: {e}")

    return True
