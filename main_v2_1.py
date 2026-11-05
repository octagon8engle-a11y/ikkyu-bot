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
from referrer_tracker import extract_referrer_id, register_user_with_referrer

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
                # ★ここにリファラー登録を仕込んでおく（プレリリース中はrefなしでも安全に動く）
                # ※もしメッセージや別の方法でrefを受け取る設計にする場合はここで抽出します
                referrer_id = extract_referrer_id({}) # 現状はNoneとして登録
                register_user_with_referrer(supabase_client, user_id, referrer_id)
                
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

    # 4. 残り回数を末尾に添える（管理者以外に表示）
    if role != "admin":
        current_remaining = get_remaining_count(supabase_client, user_id)
        ikkyu_reply_text += f"\n\n──────────────\n🍶 残り問答：{current_remaining}回"

    # 5. LINEへ返信
    line_bot_api.reply_message(reply_token, TextSendMessage(text=ikkyu_reply_text))

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    return await handle_stripe_webhook(request, supabase_client, line_bot_api)

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    html_content = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI一休さん - 草庵の迷い断ち切り所</title>
    <style>
        :root {
            --bg-color: #0f141c;
            --card-bg: #1a2230;
            --accent-gold: #d4af37;
            --text-main: #f0f4f8;
            --text-sub: #94a3b8;
            --border-color: #2a364d;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            width: 100%;
            max-width: 480px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 30px 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }
        .badge {
            display: inline-block;
            background: rgba(212, 175, 55, 0.15);
            color: var(--accent-gold);
            font-size: 0.85rem;
            padding: 4px 12px;
            border-radius: 20px;
            margin-bottom: 15px;
            border: 1px solid rgba(212, 175, 55, 0.3);
        }
        h1 {
            font-size: 1.6rem;
            margin-bottom: 15px;
            color: var(--text-main);
            letter-spacing: 0.05em;
        }
        p {
            color: var(--text-sub);
            font-size: 0.95rem;
            margin-bottom: 20px;
        }
        .section-box {
            background: rgba(15, 20, 28, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
            text-align: left;
        }
        .section-box.gold {
            border-left: 4px solid var(--accent-gold);
        }
        .section-box h3 {
            color: var(--accent-gold);
            font-size: 1rem;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .section-box ul {
            list-style-type: none;
            padding-left: 0;
        }
        .section-box li {
            font-size: 0.88rem;
            color: var(--text-main);
            margin-bottom: 6px;
            position: relative;
            padding-left: 16px;
        }
        .section-box li::before {
            content: "・";
            position: absolute;
            left: 0;
            color: var(--accent-gold);
        }
        .price-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }
        .price-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 10px;
            text-align: center;
        }
        .price-card .num {
            font-size: 1.1rem;
            font-weight: bold;
            color: var(--accent-gold);
        }
        .price-card .label {
            font-size: 0.75rem;
            color: var(--text-sub);
        }
        .pay-methods {
            font-size: 0.8rem;
            color: var(--text-sub);
            margin-top: 8px;
            line-height: 1.4;
        }
        .btn {
            display: block;
            width: 100%;
            background-color: #06c755; /* LINE Green */
            color: white;
            text-align: center;
            padding: 14px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 1.05rem;
            text-decoration: none;
            box-shadow: 0 4px 12px rgba(6, 199, 85, 0.3);
            transition: background 0.2s, transform 0.1s;
            margin-top: 10px;
            margin-bottom: 15px;
        }
        .btn:active {
            transform: scale(0.98);
        }
        .stripe-badge {
            font-size: 0.8rem;
            color: var(--text-sub);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            margin-top: 15px;
        }
        .stripe-badge span {
            color: #635bff;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container" style="text-align: center;">
        <div class="badge">📅 11/3(火)〜11/8(日) 先行プレリリース（限定10名様）</div>
        <h1>現代の草庵に生きる<br>「AI一休」</h1>
        <p>煩悩、抱えておらんか？あなたの迷いをユーモアと毒気でスパッと断ち切るLINEボット。</p>
        
        <!-- 案内 -->
        <div class="section-box gold">
            <h3>📢 プレリリース＆キャンペーン</h3>
            <ul>
                <li><strong>プレリリース期間：</strong>11月3日(火)〜11月8日(日)（限定10名様）</li>
                <li><strong>参加方法：</strong>個別に「一休」とメッセージを送ると送られてくる「合言葉（cipher）」を入力してスタート！</li>
                <li><strong>11/9(月)以降：</strong>本格解禁！LINEでお友達に紹介すると素敵な特典（ボーナス問答など）がある仕掛けを準備中！</li>
            </ul>
        </div>

        <!-- 料金・お布施システム -->
        <div class="section-box">
            <h3>🍶 料金・お布施（お酒代）システム</h3>
            <ul>
                <li><strong>参加特典：</strong>合言葉入力で問答 <strong>5回分無料</strong> 進呈！</li>
                <li><strong>問答のチャージ：</strong>お試し分終了後、冷やかしや励ましのお布施としていつでもチャージ可能。月額自動引き落とし等のサブスクではありません。</li>
            </ul>
            
            <div class="price-grid">
                <div class="price-card">
                    <div class="num">550円</div>
                    <div class="label">5回券</div>
                </div>
                <div class="price-card">
                    <div class="num">990円</div>
                    <div class="label">10回券</div>
                </div>
            </div>
        </div>

        <!-- 決済手段 -->
        <div class="section-box">
            <h3>💳 ご利用可能な決済手段</h3>
            <p class="pay-methods">
                世界基準の安全な決済システム <strong>Stripe</strong> を採用しています。<br>
                ・各種クレジットカード（Visa, Mastercard, JCB, Amex等）<br>
                ・Apple Pay / Google Pay 対応<br>
                ※クレジットカード情報は当サービス側には一切保存されません。
            </p>
        </div>

        <!-- LINE導線ボタン -->
        <a href="https://line.me/R/ti/p/@YOUR_LINE_BOT_ID" class="btn">LINEで一休さんと問答を始める</a>
        
        <div class="stripe-badge">
            🔒 決済保護：安全な <span>Stripe</span> 決済システムを採用しています
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content)
