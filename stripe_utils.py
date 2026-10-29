# stripe_utils.py
import os
import stripe
from fastapi import Request, HTTPException
from linebot.models import TextSendMessage
from ikkyu_messages import get_random_payment_message
from remaining_chats import add_user_paid_chats

# フォールバック用リンク（環境変数未設定時への備え）
STRIPE_LINK_5 = os.getenv("STRIPE_LINK_5", "https://buy.stripe.com/test_14A3cv3FjfRS5G28eAcjS00")
STRIPE_LINK_10 = os.getenv("STRIPE_LINK_10", "https://buy.stripe.com/test_3cI4gzdfT7lm7OaamIcjS01")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

def get_payment_message(user_id: str) -> str:
    """ユーザーID（client_reference_id）を付与したお布施案内文を生成"""
    url_5 = f"{STRIPE_LINK_5}?client_reference_id={user_id}"
    url_10 = f"{STRIPE_LINK_10}?client_reference_id={user_id}"
    return get_random_payment_message(url_5, url_10)

def check_usage_limit_and_get_payment(supabase_client, user_id: str, role: str):
    """
    【一般扱い統合版】利用制限チェック
    - admin のみ無制限 (True, None)
    - それ以外は一般扱いとし、無料枠(5回) + 有料追加枠を超えたら False とお布施メッセージを返す
    """
    if role == "admin":
        return True, None

    try:
        # 1. 過去の会話数を取得 (chat_logs_v1_2)
        count_resp = supabase_client.table("chat_logs_v1_2").select("id", count="exact").eq("user_id", user_id).execute()
        total_chats = count_resp.count or 0

        # 2. 購入済みの追加回数を取得
        user_resp = supabase_client.table("users_v1_2").select("paid_chats").eq("user_id", user_id).execute()
        paid_chats = 0
        if user_resp.data and len(user_resp.data) > 0:
            paid_chats = user_resp.data[0].get("paid_chats", 0) or 0

        # 無料5回 ＋ 購入分が上限
        max_allowed = 5 + paid_chats

        if total_chats >= max_allowed:
            # 上限到達：stripe_utils の機能で client_reference_id 付きリンクを生成
            return False, get_payment_message(user_id)

    except Exception as e:
        print(f"Limit check error: {e}")

    return True, None

async def handle_stripe_webhook(request: Request, supabase_client, line_bot_api=None):
    """Stripeの決済成功Webhook処理＆回数加算・LINEプッシュ通知"""
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
        user_id = session.get("client_reference_id")
        
        if not user_id:
            print("警告: client_reference_id が紐づいていません")
            return {"status": "no user_id linked"}

        amount_total = session.get("amount_total")
        add_count = 5 if amount_total == 550 else (10 if amount_total == 990 else 0)

        if add_count > 0:
            add_user_paid_chats(supabase_client, user_id, add_count)
            print(f"お布施確認! User: {user_id}, +{add_count}回追加")

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

        if add_count > 0:
            add_user_paid_chats(supabase_client, user_id, add_count)

    return {"status": "success"}
