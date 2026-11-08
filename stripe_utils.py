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

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

TX_TABLE = "stripe_transactions_v2_1"

def get_remaining_count(supabase_client, user_id: str) -> int:
    """stripe_transactions_v2_1 と chat_logs_v2_1 から残り問答数を計算"""
    try:
        # 1. 決済履歴（およびお試しボーナス・無料枠履歴）を取得
        res_tx = supabase_client.table(TX_TABLE) \
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
        
        # 3. 残り回数を算出
        remaining = total_bought - total_used
        return max(0, remaining)
    except Exception as e:
        print(f"残り回数計算エラー: {e}")
        return 0

def get_payment_message(user_id: str) -> str:
    url_5 = f"{STRIPE_LINK_5}?client_reference_id={user_id}"
    url_10 = f"{STRIPE_LINK_10}?client_reference_id={user_id}"
    return get_random_payment_message(url_5, url_10)

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
                supabase_client.table(TX_TABLE).insert({
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
