# stripe_utils.py の先頭に追加
import os
import stripe
from fastapi import Request, HTTPException
from remaining_chats import add_user_paid_chats

STRIPE_LINK_5 = os.getenv("STRIPE_LINK_5")
STRIPE_LINK_10 = os.getenv("STRIPE_LINK_10")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# stripe_utils.py に追加する Webhook 処理ロジックのイメージ
import stripe
from fastapi import Request, HTTPException, status
from remaining_chats import add_user_paid_chats  # 残数加算を担当する関数（想定）

# StripeのシークレットキーとWebhookシークレットを設定
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

async def handle_stripe_webhook(request: Request, supabase_client):
    """
    StripeからのWebhookを受け取り、決済完了時にユーザーの有料残数を加算する
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # 不正なペイロード
        raise HTTPException(status_code=400, status_html="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # 不正な署名
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 決済完了イベント（Checkout Session Completed）をキャッチ
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        # 決済リンク作成時に埋め込んだ user_id を取得
        user_id = session.get("client_reference_id")
        if not user_id:
            return {"status": "no user_id linked"}

        # 支払金額（amount_total）や商品情報から、加算する回数を判定
        # 550円 (550) -> 5回, 990円 (990) -> 10回
        amount_total = session.get("amount_total")
        
        add_count = 0
        if amount_total == 550:
            add_count = 5
        elif amount_total == 990:
            add_count = 10

        if add_count > 0:
            # remaining_chats.py 側の加算関数を呼び出してDBを更新
            add_user_paid_chats(supabase_client, user_id, add_count)

    return {"status": "success"}
