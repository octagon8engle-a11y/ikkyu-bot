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

def get_payment_message(user_id: str) -> str:
    """ユーザーID（client_reference_id）を付与したお布施案内文を生成（商品IDは含めない）"""
    url_5 = f"{STRIPE_LINK_5}?client_reference_id={user_id}"
    url_10 = f"{STRIPE_LINK_10}?client_reference_id={user_id}"
    
    # 一休さんらしい口上で綺麗にURLだけを案内するメッセージ
    return (
        "実のところ、このお寺の和尚は厳しくてのう。説法の間の一杯やるのも命がけじゃ。\n"
        "寺の裏でこっそり一杯やるための「秘密の資金」が、ちと足りなくなってしもうた。\n\n"
        "なぁに、和尚には内緒にしておくから、お前さんからこっそりお布施を頼めんか？\n\n"
        "🍶 **お布施のお品書き**\n"
        f"・ **【5回券】550円**（和尚に内緒の隠し酒代じゃ）\n{url_5}\n\n"
        f"・ **【10回券】990円**（上等なつまみで機嫌が良くなるぞ）\n{url_10}\n\n"
        "銭を包んでくれたら、秘密の極意を授けてやろう！"
    )

def check_usage_limit_and_get_payment(supabase_client, user_id: str, role: str):
    """
    【利用制限＆課金判定】
    - admin: スルー（制限なし）
    - tester: 即課金（決済URLを案内）
    - user: スルー（制限なし）
    """
    if role == "admin" or role == "user":
        return True, None

    if role == "tester":
        return False, get_payment_message(user_id)

    return True, None

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
        user_id = session.get("client_reference_id")
        session_id = session.get("id")
        amount_total = session.get("amount_total")
        
        if not user_id:
            print("警告: client_reference_id が紐づいていません")
            return {"status": "no user_id linked"}

        add_count = 5 if amount_total == 550 else (10 if amount_total == 990 else 0)

        if add_count > 0:
            # 1. stripe_transactions_test テーブルへ確実に記録
            try:
                supabase_client.table("stripe_transactions_test").insert({
                    "user_id": user_id,
                    "stripe_id": session_id,
                    "amount": amount_total,
                    "created_at": get_current_jst_str()
                }).execute()
                print(f"stripe_transactions_test に記録完了: Stripe ID {session_id}")
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
