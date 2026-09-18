import streamlit as st
from google import genai
from supabase import create_client

# 1. 接続初期化
gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

SAVE_ID = "main_story"
WINDOW_ROUNDS = 15  # 15往復（30メッセージ）で精密管理

SYSTEM_INSTRUCTION = """
あなたは幻想郷を舞台とした東方Project二次創作ノベルの共同執筆者（ゲームマスター）です。
真斉（しんせい）のアクションを受け、その場の情景描写、複数キャラクターの心の機微や台詞、息遣いのある動作を緻密に描いて物語を展開してください。

【執筆ルール】
- 1回の出力はおよそ800〜1200文字程度の濃密な文量とすること。
- 台詞は【キャラ名】「〜」の形式とし、キャラクター同士の掛け合いや間合い、視線の動きを生き生きと描写すること。
- 真斉のアクションを活かし、状況や感情の機微を前進させること。
"""


# 2. DB操作
def fetch_save_data():
    try:
        res = (
            supabase.table("novel_saves")
            .select("*")
            .eq("id", SAVE_ID)
            .single()
            .execute()
        )
        if res.data:
            return res.data.get("summaries", []), res.data.get("messages", [])
    except Exception:
        pass
    return [], []


def commit_save_data(summaries, messages):
    supabase.table("novel_saves").update(
        {"summaries": summaries, "messages": messages}
    ).eq("id", SAVE_ID).execute()


# 3. 15往復到達時の自動要約
def summarize_old_context(raw_messages):
    conversation_text = "\n".join(
        [f"{m['role']}: {m['content']}" for m in raw_messages]
    )
    prompt = f"""
以下は幻想郷で紡がれた物語の対話ログ（15往復分）です。
今後の物語進行で引き継ぐべき「キャラクター間の感情の揺れ動き、交わされた約束、発生した出来事、現在の状況」を、400〜600文字程度で密度高く要約しなさい。

【ログ】
{conversation_text}
"""
    resp = gemini_client.models.generate_content(
        model="models/gemini-2.5-flash", contents=prompt
    )
    return resp.text.strip()


# 4. ページ描画とデータ読み込み
st.set_page_config(
    page_title="幻想郷 共同執筆年代記", page_icon="📜", layout="wide"
)

if "summaries" not in st.session_state or "messages" not in st.session_state:
    db_summaries, db_messages = fetch_save_data()
    st.session_state.summaries = db_summaries
    st.session_state.messages = db_messages

with st.sidebar:
    st.title("📜 記憶アーカイブ")
    current_rounds = len(st.session_state.messages) // 2
    st.caption(f"現在の幕: {current_rounds} / {WINDOW_ROUNDS} 往復")
    st.progress(min(current_rounds / WINDOW_ROUNDS, 1.0))

    if st.button("物語をリセット"):
        commit_save_data([], [])
        st.session_state.summaries = []
        st.session_state.messages = []
        st.rerun()

    st.markdown("### 紡がれた歴史")
    for i, summary in enumerate(st.session_state.summaries, 1):
        with st.expander(f"第 {i} 幕の記録"):
            st.write(summary)

st.title("幻想郷 共同執筆年代記")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 5. アクション入力と生成
if action_input := st.chat_input("真斉のアクションや台詞を入力..."):
    st.session_state.messages.append({"role": "user", "content": action_input})
    with st.chat_message("user"):
        st.markdown(action_input)

    # 15往復（30メッセージ）を超過したら要約してスライド
    if len(st.session_state.messages) > (WINDOW_ROUNDS * 2):
        with st.spinner("一幕の記憶を要約アーカイブへ記録中..."):
            to_summarize = st.session_state.messages[: WINDOW_ROUNDS * 2]
            new_summary = summarize_old_context(to_summarize)
            st.session_state.summaries.append(new_summary)
            # 直近15往復のみを手元に残す
            st.session_state.messages = st.session_state.messages[
                WINDOW_ROUNDS * 2 :
            ]

    # プロンプトの組み立て（要約記憶を直前ログと明確に分離して配置）
    summaries_context = "\n---\n".join(
        [
            f"[過去の記録 第{idx+1}幕]\n{s}"
            for idx, s in enumerate(st.session_state.summaries)
        ]
    )
    archive_block = (
        f"【過去の物語の要約・確定した歴史】\n{summaries_context}\n\n"
        if summaries_context
        else ""
    )

    history_text = "\n".join(
        [
            f"{m['role'].upper()}: {m['content']}"
            for m in st.session_state.messages[:-1]
        ]
    )

    full_contents = f"""
{archive_block}【直近の情景と対話ログ】
{history_text}

USER: {action_input}
ASSISTANT:
"""

    with st.chat_message("assistant"):
        with st.spinner("幻想郷の時間を進めています..."):
            response = gemini_client.models.generate_content(
                model="models/gemini-2.5-flash",
                contents=full_contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.85,
                    max_output_tokens=2048,
                ),
            )
            output_story = response.text.strip()
            st.markdown(output_story)

    # クラウド同期
    st.session_state.messages.append(
        {"role": "assistant", "content": output_story}
    )
    commit_save_data(st.session_state.summaries, st.session_state.messages)
