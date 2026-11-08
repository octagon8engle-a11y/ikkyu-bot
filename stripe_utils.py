# stripe_utils.py
import os
import stripe
from fastapi import Request, HTTPException
from linebot.models import TextSendMessage
from ikkyu_messages import get_random_payment_message
from time_utils import get_current_jst_str

# 環境変数から決済リンクのURLを取得する
STRIPE_LINK_5 = os.getenv("STRIPE_LINK_5")
STRIPE_LINK_10 = os.getenv("STRIPE_LINK_10")

def get_payment_message(user_id):
    url_5 = f"{STRIPE_LINK_5}?client_reference_id={user_id}"
    url_10 = f"{STRIPE_LINK_10}?client_reference_id={user_id}"
    return url_5, url_10

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

def get_remaining_count(supabase_client, user_id: str) -> int:
    """stripe_transactions_v2_1 と chat_logs_v2_1 から残り問答数を計算"""
    try:
        # 1. 決済履歴（およびお試しボーナス履歴）を取得
        res_tx = supabase_client.table("stripe_transactions_v2_1") \
            .select("amount").eq("user_id", user_id).execute()
        
        total_bought = 0
        for tx in res_tx.data:
            amount = tx.get("amount", 0)
            if amount == 550:
                total_bought += 5
            elif amount == 990:
                total_bought += 10
            elif amount == 0:  # 新規お試しボーナス分
                total_bought += 5
                
        # 2. チャットログから使用回数を計算（chat_logs_v2_1）
        res_log = supabase_client.table("chat_logs_v2_1") \
            .select("id", count="exact").eq("user_id", user_id).execute()
        
        total_used = res_log.count if res_log.count is not None else len(res_log.data)
        
        # 3. 残り回数を算出（履歴がなければ total_bought = 0 なので即座に0回になる）
        remaining = total_bought - total_used
        return max(0, remaining)
    except Exception as e:
        print(f"残り回数計算エラー: {e}")
        return 0

def get_payment_message(user_id: str) -> str:
    url_5 = f"{STRIPE_LINK_5}?client_reference_id={user_id}"
    url_10 = f"{STRIPE_LINK_10}?client_reference_id={user_id}"
    return get_random_payment_message(url_5, url_10)

def verify_and_consume_cipher(supabase_client, user_id: str, input_cipher: str) -> bool:
    """送られてきた暗号（cipher）が有効かチェックし、使用済みにする ＋ 初回お試し5回を付与する"""
    try:
        res = supabase_client.table("cipher") \
            .select("*").eq("code", input_cipher).eq("is_used", False).execute()
        
        if res.data and len(res.data) > 0:
            cipher_record = res.data[0]
            # 使用済みに更新
            supabase_client.table("cipher").update({
                "is_used": True,
                "used_by": user_id
            }).eq("id", cipher_record["id"]).execute()
            
            # ★ここで初めて新規お試し5回分（amount=0）を付与する！
            supabase_client.table("stripe_transactions_v2_1").insert({
                "user_id": user_id,
                "stripe_id": "trial_bonus_5",
                "amount": 0,
                "fee": 0,
                "created_at": get_current_jst_str()
            }).execute()
            
            return True
    except Exception as e:
        print(f"cipher検証エラー: {e}")
    return False

def check_user_registered(supabase_client, user_id: str) -> bool:
    """すでに決済履歴やお試しボーナス、またはcipher紐づけがあるかチェック"""
    try:
        res = supabase_client.table("stripe_transactions_test") \
            .select("id", count="exact").eq("user_id", user_id).execute()
        count = res.count if res.count is not None else len(res.data)
        return count > 0
    except Exception as e:
        print(f"ユーザー登録確認エラー: {e}")
        return False

def check_usage_limit_and_get_payment(supabase_client, user_id: str, role: str):
    if role == "admin":
        return True, None, None

    if role == "tester":
        remaining = get_remaining_count(supabase_client, user_id)
        if remaining <= 0:
            return False, get_payment_message(user_id), 0
        return True, None, remaining

    return True, None, None

async def handle_stripe_webhook(request: Request, supabase_client, line_bot_api=None):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = getattr(session, "client_reference_id", None)
        session_id = getattr(session, "id", None)
        amount_total = getattr(session, "amount_total", None)
        
        if not user_id:
            return {"status": "no user_id linked"}

        add_count = 5 if amount_total == 550 else (10 if amount_total == 990 else 0)
        fee_amount = 22 if amount_total == 550 else (40 if amount_total == 990 else 0)

        if add_count > 0:
            try:
                supabase_client.table("stripe_transactions_test").insert({
                    "user_id": user_id,
                    "stripe_id": session_id,
                    "amount": amount_total,
                    "fee": fee_amount,
                    "created_at": get_current_jst_str()
                }).execute()
            except Exception as db_err:
                print(f"DB transaction log error: {db_err}")

            if line_bot_api:
                try:
                    thanks_msg = (
                        "……クックック、ありがたい冷酒代（お布施）を確かにもらったぞい！\n"
                        f"問答の回数を {add_count} 回分増やしておいた。さあ、続きを話そうぞ。"
                    )
                    line_bot_api.push_message(user_id, TextSendMessage(text=thanks_msg))
                except Exception as e:
                    print(f"LINE push error: {e}")

    return {"status": "success"}
