# stripe_utils.py
import os
import stripe
from fastapi import Request, HTTPException
from linebot.models import TextSendMessage
from ikkyu_messages import get_random_payment_message
from time_utils import get_current_jst_str

# 正しいStripeテスト決済URL
STRIPE_LINK_5 = "https://buy.stripe.com/test_14A3cv3FjfRS5G28eAcjS00"
STRIPE_LINK_10 = "https://buy.stripe.com/test_3cI4gzdfT7lm7OaamIcjS01"

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

def get_remaining_count(supabase_client, user_id: str) -> int:
    """stripe_transactions_test と chat_logs_v1_2 から残り問答数を計算"""
    try:
        # 1. 決済履歴から総購入回数を計算 (550円: 5回, 990円: 10回)
        res_tx = supabase_client.table("stripe_transactions_test") \
            .select("amount").eq("user_id", user_id).execute()
        
        total_bought = 0
        for tx in res_tx.data:
            amount = tx.get("amount", 0)
            if amount == 550:
                total_bought += 5
            elif amount == 990:
                total_bought += 10
                
        # 2. チャットログから使用回数を計算
        res_log = supabase_client.table("chat_logs_v1_2") \
            .select("id", count="exact").eq("user_id", user_id).execute()
        
        total_used = res_log.count if res_log.count is not None else len(res_log.data)
        
        # 3. 残り回数を算出
        remaining = total_bought - total_used
        return max(0, remaining)
    except Exception as e:
        print(f"残り回数計算エラー: {e}")
        return 0

def get_payment_message(user_id: str) -> str:
    """ユーザーID（client_reference_id）を付与したお布施案内文を生成"""
    url_5 = f"{STRIPE_LINK_5}?client_reference_id={user_id}"
    url_10 = f"{STRIPE_LINK_10}?client_reference_id={user_id}"
    
    return get_random_payment_message(url_5, url_10)

def check_usage_limit_and_get_payment(supabase_client, user_id: str, role: str):
    """
    【利用制限＆課金判定】
    - admin: スルー（制限なし）
    - tester: 残り回数チェック（0回以下ならお布施案内）
    """
    if role == "admin":
        return True, None, None

    if role == "tester":
        remaining = get_remaining_count(supabase_client, user_id)
        if remaining <= 0:
            return False, get_payment_message(user_id), 0
        return True, None, remaining

    # ロール未設定等も基本スルー
    return True, None, None

async def handle_stripe_webhook(request: Request, supabase_client, line_bot_api=None):
    """Stripe決済成功時のWebhook処理＆stripe_transactions_test記録・LINEプッシュ通知"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print(f"Webhook Signature Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        user_id = getattr(session, "client_reference_id", None)
        session_id = getattr(session, "id", None)
        amount_total = getattr(session, "amount_total", None)
        
        if not user_id:
            print("警告: client_reference_id が紐づいていません")
            return {"status": "no user_id linked"}

        add_count = 5 if amount_total == 550 else (10 if amount_total == 990 else 0)
        fee_amount = 22 if amount_total == 550 else (40 if amount_total == 990 else 0)

        if add_count > 0:
            # 1. stripe_transactions_test へ記録
            try:
                supabase_client.table("stripe_transactions_test").insert({
                    "user_id": user_id,
                    "stripe_id": session_id,
                    "amount": amount_total,
                    "fee": fee_amount,
                    "created_at": get_current_jst_str()
                }).execute()
                print(f"stripe_transactions_test に記録完了: Stripe ID {session_id} (Fee: {fee_amount})")
            except Exception as db_err:
                print(f"DB transaction log error: {db_err}")

            # 2. LINEプッシュ通知
            if line_bot_api:
                try:
                    thanks_msg = (
                        "……クックック、ありがたい冷酒代（お布施）を確かにもらったぞい！\n"
                        f"問答の回数を {add_count} 回分増やしておいた。さあ、続きを話そうぞ。"
                    )
                    line_bot_api.push_message(user_id, TextSendMessage(text=thanks_msg))
                except Exception as e:
                    print(f"LINE push notification error: {e}")

    return {"status": "success"}
