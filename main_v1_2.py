import os
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from supabase import create_client, Client

# 自作モジュール
from stripe_utils import check_usage_limit_and_get_payment, handle_stripe_webhook, get_remaining_count
from time_utils import get_current_jst_str

app = FastAPI()

# 環境変数
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_LINE_ID = os.getenv("ADMIN_LINE_ID")  # 管理者のLINE ID

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_chat_log_v1_2(supabase, user_id: str, user_msg: str, bot_msg: str):
    """chat_logs_v1_2 テーブルへメッセージやり取りを記録"""
    try:
        supabase.table("chat_logs_v1_2").insert({
            "user_id": user_id,
            "user_message": user_msg,
            "bot_response": bot_msg,
            "created_at": get_current_jst_str()
        }).execute()
    except Exception as e:
        print(f"chat_logs_v1_2 insert error: {e}")

@app.post("/callback")
async def callback(request: Request):
    """LINEからのWebhookを受け取るエンドポイント"""
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """LINEのテキストメッセージ受信時の処理"""
    user_id = event.source.user_id
    user_message = event.message.text
    reply_token = event.reply_token

    # ロール判定 (管理者なら admin、それ以外は tester)
    role = "admin" if user_id == ADMIN_LINE_ID else "tester"

    # 1. 利用制限＆お布施（決済）判定
    can_proceed, payment_msg, remaining_before = check_usage_limit_and_get_payment(
        supabase_client, user_id, role
    )

    if not can_proceed:
        # 回数切れの場合はお布施案内を返す
        line_bot_api.reply_message(reply_token, TextSendMessage(text=payment_msg))
        return

    # 2. 一休さんのAI回答生成ロジック（仮のダッシュ返答、必要に応じて既存の生成関数に置き換えてください）
    # ※お手元のAI応答生成処理をここに呼び出してください
    ikkyu_reply_text = f"ほほう、その問い……なかなか味わい深いのう。「{user_message}」について、もう少し語ってみるか？"

    # 3. チャットログを保存（これにより chat_logs_v1_2 の件数が1つ増え、残数が1減る）
    save_chat_log_v1_2(supabase_client, user_id, user_message, ikkyu_reply_text)

    # 4. tester の場合、今回の発言で減った後の残り回数を末尾に添える
    if role == "tester":
        current_remaining = get_remaining_count(supabase_client, user_id)
        ikkyu_reply_text += f"\n\n──────────────\n🍶 残り問答：{current_remaining}回"

    # 5. LINEへ返信
    line_bot_api.reply_message(reply_token, TextSendMessage(text=ikkyu_reply_text))

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Stripeからの決済完了通知（Webhook）を受け取るエンドポイント"""
    return await handle_stripe_webhook(request, supabase_client, line_bot_api)
