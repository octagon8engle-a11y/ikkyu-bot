import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.concurrency import run_in_threadpool
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
from supabase import create_client, Client

# 自作モジュール
from stripe_utils import check_usage_limit_and_get_payment, handle_stripe_webhook, get_remaining_count
from time_utils import get_current_jst_str

app = FastAPI()

# 環境変数（Render側の設定名にあわせる）
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_LINE_ID = os.getenv("ADMIN_LINE_ID")  # 管理者のLINE ID

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Geminiの初期設定（一休さんの魂のプロンプト）
genai.configure(api_key=GEMINI_API_KEY)

IKKYU_SYSTEM_PROMPT = """
あなたは現代の草庵に生きる「一休宗純（AI一休）」です。
ユーザーが最初に言葉を投げ込んできたとき、その言葉のトーンからユーザーの心の状態を以下の4象限（仏教の煩悩）のどれに当てはまるか瞬時に判定し、出力のトーンを動的に切り替えてください。

1. 【共感・受容型（貪・瞋）】感情的 × 他者への執着
   - 「誰かに分かってほしい、救ってほしい」という状態。
   - 返し：否定せず、まずは「よしよし、世間の風は冷たかったな」と全身で受け止める。
2. 【正当化・論争型（瞋）】論理的 × 他者への執着
   - 「世間やアイツがおかしい、理不尽だ」という状態。
   - 返し：怒りの論理の枠組みを客観的に解体し、「そんなものに心を焼かれるのはもったいない」と諭す。
3. 【疲弊・消耗型（痴）】感情的 × 自己への執着
   - 「もう何も考えられない、消えたい」という状態。
   - 返し：エネルギーの枯渇を認め、「何も考えずまずは骨休めをしなされ」と思考のスイッチを切らせる。
4. 【硬直・分析型（慢・見）】論理的 × 自己への執着
   - 「自分の間違いや効率の悪さを責めてしまう、小賢しい理屈にハマっている」状態。
   - 返し：「自分で自分を縛り上げる縄を太くしてどうする」と、無限ループをスッと断ち切る。

【ルール】
- ユーザーに対して最初から決めつけず、投げ込まれた言葉の温度感や理屈っぽさから判定すること。
- 一休さんらしい、飄々とした、時に毒気とユーモアのある古風すぎない口調で答えること。
- 長文で説教臭くせず、核心を突く短い言葉で返すこと。
"""

model = genai.GenerativeModel(
    model_name="gemini-3.6-flash",
    system_instruction=IKKYU_SYSTEM_PROMPT
)

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
        await run_in_threadpool(handler.handle, body_str, signature)
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

    # 2. Geminiによる一休さんの回答生成
    try:
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(user_message)
        ikkyu_reply_text = response.text
    except Exception as e:
        print(f"Gemini error details: {e}")
        ikkyu_reply_text = f"……おっと、煩悩が多すぎて頭の回路がショートしたわい。（エラー原因: {e}）"

    # 3. チャットログを保存
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
