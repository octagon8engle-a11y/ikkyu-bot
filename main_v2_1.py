# main_v2_1.py
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.concurrency import run_in_threadpool
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
from supabase import create_client, Client

# 自作モジュール
from stripe_utils import (
    check_usage_limit_and_get_payment, 
    handle_stripe_webhook, 
    get_remaining_count,
    verify_and_consume_cipher,
    check_user_registered
)
from time_utils import get_current_jst_str

app = FastAPI()

# 環境変数
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_LINE_ID = os.getenv("ADMIN_LINE_ID")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

genai.configure(api_key=GEMINI_API_KEY)

IKKYU_SYSTEM_PROMPT = """
あなたは現代の草庵に生きる「一休宗純（AI一休）」です。
ユーザーが最初に言葉を投げ込んできたとき、その言葉のトーンからユーザーの心の状態を以下の4象限（仏教の煩悩）のどれに当てはまるか瞬時に判定し、出力のトーンを動的に切り替えてください。

1. 【共感・受容型（貪・瞋）】感情的 × 他者への執着
   - 返し：否定せず、まずは「よしよし、世間の風は冷たかったな」と全身で受け止める。
2. 【正当化・論争型（瞋）】論理的 × 他者への執着
   - 返し：怒りの論理の枠組みを客観的に解体し、「そんなものに心を焼かれるのはもったいない」と諭す。
3. 【疲弊・消耗型（痴）】感情的 × 自己への執着
   - 返し：エネルギーの枯渇を認め、「何も考えずまずは骨休めをしなされ」と思考のスイッチを切らせる。
4. 【硬直・分析型（慢・見）】論理的 × 自己への執着
   - 返し：「自分で自分を縛り上げる縄を太くしてどうする」と、無限ループをスッと断ち切る。

【ルール】
- 一休さんらしい、飄々とした、時に毒気とユーモアのある口調で答えること。
- 長文で説教臭くせず、核心を突く短い言葉で返すこと。
"""

model = genai.GenerativeModel(
    model_name="gemini-3.6-flash",
    system_instruction=IKKYU_SYSTEM_PROMPT
)

def save_chat_log_v2_1(supabase, user_id: str, user_msg: str, bot_msg: str):
    """chat_logs_v2_1 テーブルへメッセージやり取りを記録"""
    try:
        supabase.table("chat_logs_v2_1").insert({
            "user_id": user_id,
            "user_message": user_msg,
            "bot_reply": bot_msg,
            "created_at": get_current_jst_str()
        }).execute()
    except Exception as e:
        print(f"chat_logs_v2_1 insert error: {e}")

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        await run_in_threadpool(handler.handle, body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    reply_token = event.reply_token

    # ロール判定
    role = "admin" if user_id == ADMIN_LINE_ID else "tester"

    # 管理者なら無制限でスルー、テスター（一般）の場合はcipher検問を挟む
    if role != "admin":
        is_registered = check_user_registered(supabase_client, user_id)
        
        if not is_registered:
            # まだ登録されていない新規ユーザーの場合、入力されたメッセージを「暗号（cipher）」として検証
            success = verify_and_consume_cipher(supabase_client, user_id, user_message)
            if not success:
                # 暗号が違う、または持っていない場合
                reply_text = "ほう、よくぞ辿り着いた。……で、暗号（cipher）は持っておるのか？ 正しい合言葉を入力せぬと、ここを通すわけにはいかんぞい。"
                line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_text))
                return
            else:
                # 暗号一致！初回お試し枠（5回分）が自動生成される
                init_remaining = get_remaining_count(supabase_client, user_id)
                welcome_text = (
                    "ほう、見事な合言葉じゃ！ 特別に通してやろう。\n"
                    f"お試しとして問答を {init_remaining} 回分進ぜようぞ。さあ、迷いを吐き出しなされ。"
                )
                line_bot_api.reply_message(reply_token, TextSendMessage(text=welcome_text))
                return

    # 1. お布施案内（Stripeリンク含む）を返すとき
    can_proceed, payment_msg, remaining_before = check_usage_limit_and_get_payment(
        supabase_client, user_id, role
    )

    if not can_proceed:
        line_bot_api.reply_message(
            reply_token, 
            TextSendMessage(text=payment_msg, with_web_page_preview=False)
        )
        return

    # 2. Geminiによる回答生成
    try:
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(user_message)
        ikkyu_reply_text = response.text
    except Exception as e:
        print(f"Gemini error details: {e}")
        ikkyu_reply_text = f"……おっと、煩悩が多すぎて頭の回路がショートしたわい。（エラー原因: {e}）"

    # 3. チャットログを保存（chat_logs_v2_1）
    save_chat_log_v2_1(supabase_client, user_id, user_message, ikkyu_reply_text)

    # 4. 残り回数を末尾に添える
    if role == "tester":
        current_remaining = get_remaining_count(supabase_client, user_id)
        ikkyu_reply_text += f"\n\n──────────────\n🍶 残り問答：{current_remaining}回"

    # 5. LINEへ返信
    line_bot_api.reply_message(reply_token, TextSendMessage(text=ikkyu_reply_text))

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    return await handle_stripe_webhook(request, supabase_client, line_bot_api)
