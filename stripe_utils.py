# stripe_utils.py
import os
import stripe
from fastapi import Request, HTTPException
from linebot.models import TextSendMessage
from ikkyu_messages import get_random_payment_message
from remaining_chats import add_user_paid_chats

# フォールバック用リンク
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
    【通常回数制限モード】
    - admin: 無制限
    - その他: users テーブルの count と paid_chats を参照し、無料5回＋購入分を超えたら制限
    """
    if role == "admin":
        return True, None

    try:
        # users テーブルから count と paid_chats を取得
        user_resp = supabase_client.table("users").select("count, paid_chats").eq("user_id", user_id).execute()
        
        if user_resp.data and len(user_resp.data) > 0:
            user_data = user_resp.data[0]
            current_count = user_data.get("count", 0) or 0
            paid_chats = user_data.get("paid_chats", 0) or 0

            # 無料枠（5回）＋ 購入済み追加枠 が上限
            max_allowed = 5 + paid_chats

            if current_count >= max_allowed:
                return False, get_payment_message(user_id)
        else:
            # レコードがない場合は初回扱いとして通す
            pass

    except Exception as e:
        print(f"Limit check error: {e}")

    return True, None

async def handle_stripe_webhook(request: Request, supabase_client, line_bot_api=None):
    """Stripe決済成功時のWebhook処理＆回数加算・LINEプッシュ通知"""
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
