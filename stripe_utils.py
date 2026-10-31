# stripe_utils.py
import os
import stripe
from fastapi import Request, HTTPException
from linebot.models import TextSendMessage
from ikkyu_messages import get_random_payment_message
from remaining_chats import add_user_paid_chats
from time_utils import get_current_jst_str

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
    【利用制限＆課金判定】
    - admin: 無制限
    - tester: お試しなし（無料枠5回なし、購入分 paid_chats を超えたら即決済へ）
    - その他: 無料5回 ＋ 購入分(paid_chats) が上限
    """
    if role == "admin":
        return True, None

    try:
        user_resp = supabase_client.table("users").select("count, paid_chats").eq("user_id", user_id).execute()
        
        current_count = 0
        paid_chats = 0
        if user_resp.data and len(user_resp.data) > 0:
            user_data = user_resp.data[0]
            current_count = user_data.get("count", 0) or 0
            paid_chats = user_data.get("paid_chats", 0) or 0

        # ロール別の許容回数計算
        if role == "tester":
            max_allowed = paid_chats  # お試しなし（無料枠なし）
        else:
            max_allowed = 5 + paid_chats  # 一般ユーザーは無料5回＋購入分

        if current_count >= max_allowed:
            return False, get_payment_message(user_id)

    except Exception as e:
        print(f"Limit check error: {e}")

    return True, None

async def handle_stripe_webhook(request: Request, supabase_client, line_bot_api=None):
    """Stripe決済成功時のWebhook処理＆回数加算・stripe_transactions_test記録・LINEプッシュ通知"""
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
            # 1. ユーザーの購入回数（paid_chats）を増やす
            add_user_paid_chats(supabase_client, user_id, add_count)
            print(f"お布施確認! User: {user_id}, +{add_count}回追加")

            # 2. stripe_transactions_test テーブルへ確実に記録
            try:
                supabase_client.table("stripe_transactions_test").insert({
                    "user_id": user_id,
                    "session_id": session_id,
                    "amount": amount_total,
                    "add_count": add_count,
                    "created_at": get_current_jst_str()
                }).execute()
                print(f"stripe_transactions_test に記録完了: Session {session_id}")
            except Exception as db_err:
                print(f"DB transaction log error: {db_err}")

            # 3. LINEプッシュ通知
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
