# ユーザー情報取得
user = get_user(user_id)
remaining = user.get("remaining_chats", 5)
role = user.get("role")

if role == "admin":
    # adminは制限なしで会話OK
    process_chat()
elif remaining > 0:
    # 残数を1減らして会話
    update_user_remaining_chats(user_id, remaining - 1)
    process_chat()
else:
    # 0回以下ならStripe購入リンクを返信
    send_stripe_payment_links(user_id)
