from datetime import datetime, timezone, timedelta
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.concurrency import run_in_threadpool
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
import google.generativeai as genai
from supabase import create_client, Client
import uvicorn

app = FastAPI()

# 環境変数からの読み込み
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

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
- 一休さんらしい、飄々とした、時に毒気とユーモアのある口調（古風すぎず、かつ軽すぎないトーン）で答えること。
- 長文で説教臭くせず、核心を突く短い言葉で返すこと。
"""

model = genai.GenerativeModel(
    model_name="gemini-3.6-flash",
    system_instruction=IKKYU_SYSTEM_PROMPT
)

# Supabaseの初期設定
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# スリープ対策
@app.get("/")
async def root():
    return {"status": "AI Ikkyu Test Mode is awake"}

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

# 友達追加（フォロー）された時のイベント
@handler.add(FollowEvent)
def handle_follow(event):
    welcome_message = "……ふむ。何があった？"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=welcome_message)
    )

# 通常のメッセージ受信時
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    
    # 1. ロール判定の取得（未登録なら 'F'）
    role = "F"
    try:
        user_resp = supabase.table("users").select("role").eq("user_id", user_id).execute()
        if user_resp.data:
            role = user_resp.data[0].get("role", "F")
    except Exception as e:
        print(f"Role fetch error: {e}")

    # 2. admin 以外は 1日5回制限のチェックを実施
    if role != "admin":
        try:
            # 日本時間の本日の開始時刻（00:00:00）を算出し、UTCに変換して比較
            jst = timezone(timedelta(hours=9))
            now_jst = datetime.now(jst)
            today_start_jst = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
            today_start_utc = today_start_jst.astimezone(timezone.utc).isoformat()

            # テスト用テーブル（chat_logs_test）から本日分の利用回数をカウント
            count_resp = supabase.table("chat_logs_test") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .gte("created_at", today_start_utc) \
                .execute()
            
            today_count = count_resp.count or 0

            if today_count >= 5:
                limit_message = "本日の利用制限（5回）に達したわい。\n午前0時（日本時間）になればリセットされるから、また明日来なされ。"
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=limit_message)
                )
                return
        except Exception as e:
            print(f"Limit check error: {e}")

    # 3. Geminiで返答生成
    try:
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(user_message)
        reply_text = response.text
    except Exception as e:
        print(f"Gemini error details: {e}")
        reply_text = f"……おっと、煩悩が多すぎて頭の回路がショートしたわい。（エラー原因: {e}）"

    # 4. テスト用テーブル（chat_logs_test）に会話ログを保存
    try:
        supabase.table("chat_logs_test").insert({
            "user_id": user_id,
            "user_message": user_message,
            "bot_reply": reply_text,
            "role": role
        }).execute()
    except Exception as e:
        print(f"Database error: {e}")
    
    # 5. LINEへ返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# ポートのバインド処理
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main_v1_1:app", host="0.0.0.0", port=port)
