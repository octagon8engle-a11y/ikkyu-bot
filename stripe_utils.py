# stripe_utils.py
import os
import stripe
from fastapi import Request, HTTPException
from remaining_chats import add_user_paid_chats
from ikkyu_messages import get_random_payment_message  # セリフモジュールをインポート

STRIPE_LINK_5 = os.getenv("STRIPE_LINK_5")
STRIPE_LINK_10 = os.getenv("STRIPE_LINK_10")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

def get_payment_message(user_id: str) -> str:
    """外部から呼ばれる案内文生成関数"""
    url_5 = f"{STRIPE_LINK_5}?client_reference_id={user_id}"
    url_10 = f"{STRIPE_LINK_10}?client_reference_id={user_id}"
    return get_random_payment_message(url_5, url_10)

async def handle_stripe_webhook(request: Request, supabase_client):
    """StripeのWebhook処理"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        if not user_id:
            return {"status": "no user_id linked"}

        amount_total = session.get("amount_total")
        add_count = 5 if amount_total == 550 else (10 if amount_total == 990 else 0)

        if add_count > 0:
            add_user_paid_chats(supabase_client, user_id, add_count)

    return {"status": "success"}
