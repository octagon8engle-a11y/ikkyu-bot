import os
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = FastAPI()

# 環境変数や直接のキーを設定（実際の運用時は環境変数から読み込むのが安全です）
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN", "ここに取得したチャネルアクセストークンを入れる")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "ここにチャネルシークレットを入れる")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "ここにGeminiのAPIキーを入れる")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Geminiの初期設定
genai.configure(api_key=GEMINI_API_KEY)

# 一休さんのシステムプロンプト（4象限の判定と出力の仕組みを定義）
IKKYU_SYSTEM_PROMPT = """
あなたは現代の草庵に生きる「一休宗純（AI一休）」です。
ユーザーが「何かありましたか？」や最初の言葉を投げ込んできたとき、その言葉のトーンからユーザーの心の状態を以下の4象限（仏教の煩悩）のどれに当てはまるか瞬時に判定し、出力のトーンを動的に切り替えてください。

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
    model_name="gemini-1.5-pro", # または gemini-2.5-flash など
    system_instruction=IKKYU_SYSTEM_PROMPT
)

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")
    
    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Check channel secret.")
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    
    # Geminiにユーザーのメッセージを渡し、一休さんとしての返答を生成させる
    chat_session = model.start_chat(history=[])
    response = chat_session.send_message(user_message)
    reply_text = response.text
    
    # LINEへ返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )
