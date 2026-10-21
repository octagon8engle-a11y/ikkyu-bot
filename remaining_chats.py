# remaining_chats.py

# 必要な関数（あらかじめ用意されているSupabase操作関数など）のインポート
# from db import get_user, update_user_remaining_chats, process_chat, send_stripe_payment_links

def process_user_chat_count(user_id: str, supabase_client=None):
    """
    ユーザーの残数をチェックし、消費またはStripe案内を行う関数
    """
    # ユーザー情報を取得
    user = get_user(user_id)
    
    # Supabaseのテーブル定義に合わせてカラム名を調整（free_chats_left や paid_chats_leftなど）
    # ここでは仮に remaining_chats として進めます
    remaining = user.get("remaining_chats", 5)
    role = user.get("role")

    if role == "admin":
        # adminは制限なしで会話OK
        process_chat()
        return True
    elif remaining > 0:
        # 残数を1減らして会話
        update_user_remaining_chats(user_id, remaining - 1)
        process_chat()
        return True
    else:
        # 0回以下ならStripe購入リンクを返信
        send_stripe_payment_links(user_id)
        return False
