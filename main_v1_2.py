# main_v1_2.py
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.concurrency import run_in_threadpool
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
import google.generativeai as genai
from supabase import create_client, Client
import uvicorn

# 分離したモジュールからインポート
from time_utils import get_current_jst_str
from stripe_utils import handle_stripe_webhook, check_usage_limit_and_get_payment

app = FastAPI()

# 環境変数からの読み込み
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Geminiの初期設定（3.6固定）
genai.configure(api_key=GEMINI_API_KEY)

IKKYU_SYSTEM_PROMPT = """
あなたは現代の草庵に生きる「一休宗純（AI一休）」です。
ユーザーが最初に言葉を投げ込んできたとき、その言葉のトーンからユーザーの心の状態を以下の4象限（仏教の煩悩）のどれに当てはまるか瞬時に判定し、出力のトーンを動的に切り替えてください。

1. 【共感・受容型（貪・瞋）】感情的 × 他者への執着
   - 返し：否定せず、まずは「よしよし、世間の風は冷たかったな」と全身で受け止める。
2. 【正当化・論争型（瞋）】論理的 × 他者への執着
   - 返し：怒りの論理の枠組みを客観的に解体し、「そんなものに心を焼かれるのはもったいない」と諭す。
3. 【疲弊・消耗型（痴）】感情的 × 自己への執着
   - 返し：エネルギーの枯渇を認め、「何も考えずまずは骨休めをしなされ」と思思考のスイッチを切らせる。
4. 【硬直・分析型（慢・見）】論理的 × 自己への執着
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

# Supabaseの初期設定
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.get("/")
async def root():
    return {"status": "AI Ikkyu v1.2 Tester Mode is awake"}


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")
    
    try:
        await run_in_threadpool(handler.handle, body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Check channel secret.")
    return "OK"


# Stripe Webhookエンドポイント
@app.post("/stripe/webhook")
@app.post("/stripe-webhook")
async def stripe_webhook_endpoint(request: Request):
    print("--- [Stripe Webhook 受信] リクエストが届きました ---")
    return await handle_stripe_webhook(request, supabase, line_bot_api)


@handler.add(FollowEvent)
def handle_follow(event):
    welcome_message = "……ふむ。何があった？"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=welcome_message)
    )


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

# --- メッセージ受信ハンドラ内 ---

# 1. 利用制限チェック
can_proceed, payment_msg, remaining_before = check_usage_limit_and_get_payment(supabase_client, user_id, role)

if not can_proceed:
    # 残り0回ならお布施案内を返す
    line_bot_api.reply_message(reply_token, TextSendMessage(text=payment_msg))
    return

# 2. 一休さんのAI回答生成 & chat_logs_v1_2 にログ保存
ikkyu_reply_text = generate_ikkyu_response(...) 

save_chat_log_v1_2(supabase_client, user_id, user_message, ikkyu_reply_text)

# 3. 返信メッセージの組み立て（tester の場合、今回の発言で1減った後の残数を表示）
if role == "tester":
    # ログ保存後の正確な残数を取得（または remaining_before - 1）
    current_remaining = get_remaining_count(supabase_client, user_id)
    ikkyu_reply_text += f"\n\n──────────────\n🍶 残り問答：{current_remaining}回"

# 4. LINEへ返信
line_bot_api.reply_message(reply_token, TextSendMessage(text=ikkyu_reply_text))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main_v1_2:app", host="0.0.0.0", port=port)
