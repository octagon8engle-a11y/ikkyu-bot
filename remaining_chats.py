# remaining_chats.py

def process_user_chat_count(supabase, user_id: str) -> bool:
    """
    ユーザーの残数をチェックし、
    無料枠があれば無料枠を1減らし、
    無料が0なら有料枠を1減らし、
    両方0ならFalseを返す（Stripe誘導用）
    """
    # 1. ユーザーデータを取得（存在しない場合は新規作成するなどの処理があってもOK）
    response = supabase.table("users_v1_2").select("*").eq("user_id", user_id).execute()
    
    if not response.data:
        # ユーザーがDBにいない場合の初期化（無料5回）
        new_user = {
            "user_id": user_id,
            "free_chats_left": 5,
            "paid_chats_left": 0,
            "role": "user"
        }
        supabase.table("users_v1_2").insert(new_user).execute()
        user = new_user
    else:
        user = response.data[0]

    role = user.get("role", "user")
    free_left = user.get("free_chats_left", 0)
    paid_left = user.get("paid_chats_left", 0)

    # 2. adminは無制限
    if role == "admin":
        return True

    # 3. 無料枠がある場合 -> 無料枠を1減らす
    if free_left > 0:
        supabase.table("users_v1_2").update({"free_chats_left": free_left - 1}).eq("user_id", user_id).execute()
        return True

    # 4. 有料枠がある場合 -> 有料枠を1減らす
    elif paid_left > 0:
        supabase.table("users_v1_2").update({"paid_chats_left": paid_left - 1}).eq("user_id", user_id).execute()
        return True

    # 5. 両方0の場合 -> チャット不可（Stripe案内へ）
    else:
        return False


def add_user_paid_chats(supabase, user_id: str, add_count: int):
    """
    Stripe決済完了時に、有料チャット残数を加算する関数（Webhookから呼ばれる）
    """
    response = supabase.table("users_v1_2").select("paid_chats_left").eq("user_id", user_id).execute()
    
    if response.data:
        current_paid = response.data[0].get("paid_chats_left", 0)
        new_paid = current_paid + add_count
        
        # 加算してアップデート
        supabase.table("users_v1_2").update({"paid_chats_left": new_paid}).eq("user_id", user_id).execute()
