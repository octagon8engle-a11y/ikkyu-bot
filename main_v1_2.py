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

# 分離したモジュールからインポート（referrer_trackerも追加）
from time_utils import get_current_jst_str
from role_utils import get_user_role
from limit_utils import check_usage_limit
from ikkyu_messages import get_random_payment_message
from referrer_tracker import extract_referrer_id, register_user_with_referrer
from stripe_utils import handle_stripe_webhook

app = FastAPI()

# main_v1_2.py
from stripe_utils import handle_stripe_webhook

@app.post("/stripe-webhook")
async def stripe_webhook_endpoint(request: Request):
    return await handle_stripe_webhook(request, supabase)

# 環境変数からの読み込み
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Stripeの決済リンク（Renderの環境変数から取得）
STRIPE_LINK_5 = os.getenv("STRIPE_LINK_5", "https://buy.stripe.com/test_550")
STRIPE_LINK_10 = os.getenv("STRIPE_LINK_10", "https://buy.stripe.com/test_990")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Geminiの初期設定
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

# Supabaseの初期設定
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.get("/")
async def root():
    return {"status": "AI Ikkyu v1.2 Identifier & Attribution Mode is awake"}

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

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    # フォロー時に初期ユーザー登録（必要に応じて紹介者IDを紐づける基盤）
    register_user_with_referrer(supabase, user_id, referrer_id=None)
    
    welcome_message = "……ふむ。何があった？"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=welcome_message)
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    
    # 1. ロール判定の取得
    role = get_user_role(supabase, user_id)

     # 2. 回数制限のチェック（adminならスルーされる仕様）
    is_allowed = check_usage_limit(supabase, user_id, role)
    if not is_allowed:
        # ikkyu_messages.py からランダムに酒好きおねだり文面を生成
        limit_message = get_random_payment_message(STRIPE_LINK_5, STRIPE_LINK_10)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=limit_message)
        )
        return

    # 3. Geminiで返答生成
    try:
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(user_message)
        reply_text = response.text
    except Exception as e:
        print(f"Gemini error details: {e}")
        reply_text = f"……おっと、煩悩が多すぎて頭の回路がショートしたわい。（エラー原因: {e}）"

    # 4. ログの保存先（chat_logs_v1_2）に保存（referrer_idやturn_countも含める構造に対応）
    try:
        # ユーザーの最新のreferrer_idを取得してログに焼き込む
        user_record = supabase.table("users_v1_2").select("referrer_id").eq("user_id", user_id).execute()
        ref_id = user_record.data[0].get("referrer_id") if user_record.data else None

        supabase.table("chat_logs_v1_2").insert({
            "user_id": user_id,
            "user_message": user_message,
            "bot_reply": reply_text,
            "role": role,
            "referrer_id": ref_id,
            "created_at": get_current_jst_str()
        }).execute()
    except Exception as e:
        print(f"Database error: {e}")
    
    # 5. LINEへ返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main_v1_2:app", host="0.0.0.0", port=port)
