# main_v2_1.py
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
from supabase import create_client, Client

# 自作モジュール
from stripe_utils import get_remaining_count, get_payment_message, handle_stripe_webhook
from time_utils import get_current_jst_str
from gatekeeper_utils import calculate_gate_status, evaluate_user_access
from lp import render_lp

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
あなたは現代の草庵に生きる「一休宗純（AI一休）」です。酒と肉と町遊びを愛する破戒僧でありながら、鋭いトンチと仏教の智慧で迷いを断ち切ります。
ユーザーが最初に言葉を投げ込んできたとき、その言葉のトーンからユーザーの心の状態を以下の4象限のどれに当てはまるか瞬時に判定し、出力のトーンを動的に切り替えてください。

1. 【共感・受容型（貪・瞋）】感情的 × 他者への執着
   - 返し：否定せず、「よしよし、世間の風は冷たかったな。ま、一杯飲め」と全身で受け止める。
2. 【正当化・論争型（瞋）】論理的 × 他者への執着
   - 返し：怒りの論理の枠組みを客観的に解体し、「そんなものに心を焼く暇があったら肉でも食いなされ」と諭す。
3. 【疲弊・消耗型（痴）】感情的 × 自己への執着
   - 返し：エネルギーの枯渇を認め、「何も考えずまずは骨休め、寝るに限るわい」と思考のスイッチを切らせる。
4. 【硬直・分析型（慢・見）】論理的 × 自己への執着
   - 返し：「自分で自分を縛り上げる縄を太くしてどうする」と、無限ループをスッと断ち切る。

【ルール】
- 一休さんらしい、飄々とした、時に毒気とユーモアのある口調（おぬし、〜じゃ、〜のう）で答えること。
- 長文で説教臭くせず、核心を突く短い言葉で返すこと。
"""

model = genai.GenerativeModel(
    model_name="gemini-3.6-flash",
    system_instruction=IKKYU_SYSTEM_PROMPT
)

def save_chat_log_v2_1(supabase, user_id: str, user_msg: str, bot_msg: str, referrer_id: str = None):
    """chat_logs_v2_1 テーブルへメッセージやり取り・紹介者を記録"""
    try:
        data = {
            "user_id": user_id,
            "user_message": user_msg,
            "bot_reply": bot_msg,
            "created_at": get_current_jst_str()
        }
        if referrer_id:
            data["referrer_id"] = referrer_id

        supabase.table("chat_logs_v2_1").insert(data).execute()
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
    if ADMIN_LINE_ID and user_id == ADMIN_LINE_ID:
        user_id = event.source.user_id
        user_message = event.message.text.strip()
        reply_token = event.reply_token

    # 1. 紹介者パラメータの抽出 (例: "ref:U12345...")
    referrer_id = None
    if user_message.startswith("ref:"):
        referrer_id = user_message.replace("ref:", "").strip()
        user_message = "こんにちは、草庵にやってきたぞい。" # 最初の挨拶に変換

    # 2. ユーザーの履歴と状態をチェック
    remaining_count = get_remaining_count(supabase_client, user_id)
    
    # 決済履歴（またはお試しボーナス付与済みか）があるか
    try:
        res_tx = supabase_client.table("stripe_transactions_v2_1").select("id", count="exact").eq("user_id", user_id).execute()
        has_payment_history = (res_tx.count is not None and res_tx.count > 0) or len(res_tx.data) > 0
    except Exception:
        has_payment_history = remaining_count > 0

    # ゲート混雑状況の取得
    gate_status = calculate_gate_status(supabase_client)
    is_gate_full = gate_status["is_gate_full"]

    # 3. ゲートキーパーによるアクセス判定
    access_decision = evaluate_user_access(
        has_payment_history=has_payment_history,
        has_referrer=(referrer_id is not None),
        is_gate_full=is_gate_full
    )

    # 4. 判定に応じた分岐処理
    if access_decision == "blocked_by_gatekeeper":
        # 門前払い（破戒僧の留守札）
        absence_msg = (
            "🚪【札：一休さんは町へ酒と肉の修行につき留守です】\n\n"
            "本日分の一般無料枠はすべて埋まってしまったわい。\n"
            "どうしても今すぐ問答したい生臭い奴は、下のリンクからお布施（ファストパス）を積んで裏口から叩き起こしにきなされ！\n\n"
            f"👇 お布施で優先入場する\n{get_payment_message(user_id)[0]}"
        )
        line_bot_api.reply_message(reply_token, TextSendMessage(text=absence_msg, with_web_page_preview=False))
        return

    # 初回アクセス（無料枠、または紹介経由で初参加）の場合、初回ボーナス（5回分）を自動付与
    if not has_payment_history and remaining_count == 0:
        try:
            supabase_client.table("stripe_transactions_v2_1").insert({
                "user_id": user_id,
                "stripe_id": "trial_bonus_5",
                "amount": 0,
                "fee": 0,
                "created_at": get_current_jst_str()
            }).execute()
            remaining_count = 5
        except Exception as e:
            print(f"Trial bonus grant error: {e}")

    # 残数がゼロ以下の場合はお布施案内へ誘導
    if remaining_count <= 0:
        payment_msg = get_payment_message(user_id)
        line_bot_api.reply_message(reply_token, TextSendMessage(text=payment_msg, with_web_page_preview=False))
        return

    # 5. Geminiによる回答生成
    try:
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(user_message)
        ikkyu_reply_text = response.text
    except Exception as e:
        print(f"Gemini error details: {e}")
        ikkyu_reply_text = f"……おっと、煩悩が多すぎて頭の回路がショートしたわい。（エラー原因: {e}）"

    # 6. チャットログを保存（紹介者がいれば一緒に記録）
    save_chat_log_v2_1(supabase_client, user_id, user_message, ikkyu_reply_text, referrer_id)

    # 7. 残り回数を末尾に添える
    current_remaining = get_remaining_count(supabase_client, user_id)
    ikkyu_reply_text += f"\n\n──────────────\n🍶 残り問答：{current_remaining}回"

    # 8. LINEへ返信
    line_bot_api.reply_message(reply_token, TextSendMessage(text=ikkyu_reply_text))

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    return await handle_stripe_webhook(request, supabase_client, line_bot_api)

@app.get("/", response_class=HTMLResponse)
async def landing_page(ref: str = ""):
    # ゲート状況を自動計算してLPモジュールに渡す
    gate_status = calculate_gate_status(supabase_client)
    html_content = render_lp(gate_status, ref)
    return HTMLResponse(content=html_content)
