import os
from supabase import create_client, Client
import google.generativeai as genai

# 環境変数からの読み込み
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 初期設定
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# トークン計算用にモデルをロード
model = genai.GenerativeModel(model_name="gemini-3.6-flash")

def backfill_missing_tokens():
    print("トークンが未設定（NULLまたは0）のレコードを検索中...")
    
    # 1. prompt_tokens が NULL または 0 のレコードを取得
    response = supabase.table("chat_logs_v1_1") \
        .select("id, user_message, bot_reply") \
        .or_("prompt_tokens.is.null,prompt_tokens.eq.0") \
        .execute()
    
    records = response.data
    if not records:
        print("対象となるレコードはありませんでした。すべて計算済みです！")
        return

    print(f"対象レコード数: {len(records)} 件。トークンの計算と更新を開始します...\n")

    for record in records:
        record_id = record["id"]
        user_message = record.get("user_message", "")
        bot_reply = record.get("bot_reply", "")

        prompt_tokens = 0
        candidate_tokens = 0
        total_tokens = 0

        try:
            # 再びGeminiのチャットまたはモデルでテキストから正確なトークン数を算出・取得する
            # ※過去のやり取りを再現して正確なusage_metadataを取るため、chat_sessionを使用
            chat_session = model.start_chat(history=[])
            res = chat_session.send_message(user_message)
            
            # もし bot_reply がすでに存在する場合は、AI側のレスポンスを生成し直すより
            # モデルの count_tokens を使うとAPIを節約しつつ正確に測れます
            p_tokens_res = model.count_tokens(user_message)
            c_tokens_res = model.count_tokens(bot_reply if bot_reply else res.text)
            
            prompt_tokens = p_tokens_res.total_tokens
            candidate_tokens = c_tokens_res.total_tokens
            total_tokens = prompt_tokens + candidate_tokens

            # Supabaseの該当レコードをアップデート
            supabase.table("chat_logs_v1_1").update({
                "prompt_tokens": prompt_tokens,
                "candidate_tokens": candidate_tokens,
                "total_tokens": total_tokens
            }).eq("id", record_id).execute()

            print(f"[ID: {record_id}] 更新完了 -> prompt: {prompt_tokens}, candidate: {candidate_tokens}, total: {total_tokens}")

        except Exception as e:
            print(f"[ID: {record_id}] エラー発生: {e}")

    print("\nすべての未設定レコードの処理が完了しました！")

if __name__ == "__main__":
    backfill_missing_tokens()
