import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client

# 1. 接続初期化
gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

SAVE_ID = "main_story"
WINDOW_ROUNDS = 15  # 15往復（30メッセージ）を一幕として管理

SYSTEM_INSTRUCTION = """
あなたは幻想郷を舞台とした東方Project二次創作成人向けノベルの共同執筆者（ゲームマスター）です。
真斉（しんせい）のアクションを受け、その場の情景描写、複数キャラクターの心の機微や台詞、息遣いのある動作を緻密に描いて物語を展開してください。
【真斉の設定】
- 20代後半の顔立ちの良い青年で、少し細身で鍛えている。

【執筆ルール】
- 1回の出力はおよそ800〜1200文字程度の濃密な文量とすること。
- 台詞は キャラ名「〜」の形式とし、キャラクター同士の掛け合いや間合い、視線の動きを生き生きと描写すること。
- 文章の一番最初に日時(〇年〇月〇日、24；00表記)と場所、天候を箇条書きに描写すること。
- 真斉のアクションを活かし、状況や感情の機微を前進させること。
- 真斉のアクションに逆らうキャラクターの動きも描写し、必ずしも真斉の意向通りになるのではなく、あくまでキャラクターそれぞれの思考を活かした描写をすること。
- 官能的な描写や流れは無理に作らず、自然に描写すること。描写する際は直接的な性描写も含めること。快感の表現には♡を使うこと。
- キャラ名(～)の形式で描かれる心理描写は個人の思考であり、キャラクターそれぞれの中でしか認識できない。これは心を読む能力によってのみ暴かれる。
- キャラクターは東方Projectの設定から考えられる人格であり、知性も原作を踏襲し、自然な会話を描写すること。キャラクターが生きた長さを実感させる知見あるいは未熟な部分を描写してキャラクターの実感を持たせること。
- キャラクターの日常や幻想郷の日常を極端に曲げないこと。
"""

# セーフティフィルターの制限を全解除
CUSTOM_SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
]


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
今後の物語進行で引き継ぐべき「キャラクター間の感情の揺れ動き、交わされた約束、発生した出来事、現在の状況」を密度高く要約しなさい。

【出力フォーマット】
1行目：この一幕の出来事を象徴する魅力的な見出し（20文字以内、例：【魔法の森の邂逅とアリスの実験】）
2行目以降：400〜600文字程度の要約本文

【ログ】
{conversation_text}
"""
    try:
        resp = gemini_client.models.generate_content(
            model="models/gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                safety_settings=CUSTOM_SAFETY_SETTINGS
            ),
        )
        if resp.text:
            return resp.text.strip()
    except Exception:
        pass
    return "【記憶の欠損】\n当時の記憶を記録する際に霧が発生したようだ。"


# 4. ページ描画とデータ読み込み
st.set_page_config(page_title="幻想郷 真斉幻想禄", page_icon="📜", layout="wide")

# 小説用スタイル調整（真斉の文章のみ色をトーンダウン）
st.markdown(
    """
    <style>
    .stMarkdown p {
        font-size: 1.08rem !important;
        line-height: 1.95 !important;
        letter-spacing: 0.03em !important;
        margin-bottom: 1.4em !important;
    }
    /* 真斉の入力部分：少し暗めの落ち着いたソフトグレー */
    .user-entry, .user-entry p {
        color: #8c95a0 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

if "summaries" not in st.session_state or "messages" not in st.session_state:
    db_summaries, db_messages = fetch_save_data()
    st.session_state.summaries = db_summaries
    st.session_state.messages = db_messages

current_act = len(st.session_state.summaries) + 1

for m in st.session_state.messages:
    if "act" not in m:
        m["act"] = current_act

if "selected_act" not in st.session_state:
    st.session_state.selected_act = None

current_act_messages = [
    m for m in st.session_state.messages if m.get("act") == current_act
]
act_rounds = len(current_act_messages) // 2
total_rounds = (len(st.session_state.summaries) * WINDOW_ROUNDS) + act_rounds
remaining = WINDOW_ROUNDS - act_rounds
progress_val = min(act_rounds / WINDOW_ROUNDS, 1.0)


# 役割に応じてトーンを分けるレンダラー
def display_novel_entry(role, content):
    if role == "user":
        st.markdown(
            f'<div class="user-entry">\n\n{content}\n\n</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(content)


with st.sidebar:
    st.title("📜 記憶アーカイブ")

    if st.session_state.selected_act is not None:
        if st.button(
            "↩ 現在へ戻る（最新の執筆画面へ）",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.selected_act = None
            st.rerun()
    else:
        st.caption("📍 現在: 最新の幕を執筆中")

    st.markdown(
        f"### 第 **{current_act}** 幕: **{act_rounds}** / {WINDOW_ROUNDS} 往復"
    )
    st.progress(progress_val)
    st.caption(
        f"💡 次の要約アーカイブまで **あと {remaining} 往復**（累計: {total_rounds} 往復）"
    )

    if st.button("物語をリセット"):
        commit_save_data([], [])
        st.session_state.summaries = []
        st.session_state.messages = []
        st.session_state.selected_act = None
        st.rerun()

    st.markdown("---")
    st.markdown("### 紡がれた歴史")
    for idx, summary in enumerate(st.session_state.summaries):
        lines = summary.strip().split("\n", 1)
        if len(lines) > 1 and (lines[0].startswith("【") or len(lines[0]) <= 30):
            header_title = lines[0].strip("【】 ")
            body_text = lines[1].strip()
        else:
            header_title = "未題の幕"
            body_text = summary

        with st.expander(f"第 {idx + 1} 幕の記録 - {header_title}"):
            if st.button(
                f"📖 当時の記憶を見る（第 {idx + 1} 幕）",
                key=f"view_act_btn_{idx}",
                use_container_width=True,
            ):
                st.session_state.selected_act = idx
                st.rerun()

            new_title = st.text_input(
                "見出し（サブタイトル）",
                value=header_title,
                key=f"title_{idx}",
            )
            new_body = st.text_area(
                "要約本文", value=body_text, height=180, key=f"body_{idx}"
            )

            if st.button("この記録を保存", key=f"save_summary_btn_{idx}"):
                combined = f"【{new_title}】\n{new_body}"
                st.session_state.summaries[idx] = combined
                commit_save_data(
                    st.session_state.summaries, st.session_state.messages
                )
                st.toast(
                    f"第 {idx + 1} 幕の記録を『{new_title}』として更新しました！"
                )
                st.rerun()

# 5. メイン画面の描画
if st.session_state.selected_act is not None:
    # --- 【回想モード】 ---
    act_idx = st.session_state.selected_act
    target_act = act_idx + 1
    col_t, col_b = st.columns([4, 1])
    with col_t:
        st.title(f"📖 第 {target_act} 幕の記憶（回想中）")
    with col_b:
        if st.button(
            "↩ 現在へ", key="back_to_present_main", use_container_width=True
        ):
            st.session_state.selected_act = None
            st.rerun()

    reminiscence_messages = [
        m for m in st.session_state.messages if m.get("act") == target_act
    ]
    if reminiscence_messages:
        for msg in reminiscence_messages:
            display_novel_entry(msg["role"], msg["content"])
    else:
        st.info(
            f"💡 第 {target_act} 幕の生ログは、完全保存機能の導入前の幕のため保管されていません。左サイドバーの「要約本文」から当時の記録をお楽しみください。"
        )

else:
    # --- 【通常モード】 ---
    st.title("幻想郷 真斉幻想禄")

    for msg in current_act_messages:
        display_novel_entry(msg["role"], msg["content"])

    if action_input := st.chat_input("物語の続きを執筆..."):
        user_msg = {
            "role": "user",
            "content": action_input,
            "act": current_act,
        }
        st.session_state.messages.append(user_msg)
        display_novel_entry("user", action_input)

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

        recent_messages = st.session_state.messages[
            -(WINDOW_ROUNDS * 2 + 1) : -1
        ]
        history_text = "\n".join(
            [f"{m['role'].upper()}: {m['content']}" for m in recent_messages]
        )

        full_contents = f"""
{archive_block}【直近の情景と対話ログ】
{history_text}

USER: {action_input}
ASSISTANT:
"""

        with st.spinner("幻想郷の時間を進めています..."):
            try:
                response = gemini_client.models.generate_content(
                    model="models/gemini-3.8-flash",
                    contents=full_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.85,
                        max_output_tokens=2048,
                        safety_settings=CUSTOM_SAFETY_SETTINGS,
                    ),
                )
                output_story = response.text.strip() if response.text else None
            except Exception as e:
                output_story = None

        # 安全ガード：もしGeminiからテキストが返らなかった場合の処理
        if not output_story:
            # 入力失敗として直前のユーザー入力を巻き戻す
            st.session_state.messages.pop()
            st.error(
                "⚠️ 物語の生成が中断されました。リミット解除しましたがそれでも表現が安全基準に触れたか、APIが一時的に混雑している可能性があります。直前の入力を少し言い換えてもう一度お試しください。"
            )
        else:
            display_novel_entry("assistant", output_story)

            assistant_msg = {
                "role": "assistant",
                "content": output_story,
                "act": current_act,
            }
            st.session_state.messages.append(assistant_msg)

            updated_act_messages = [
                m
                for m in st.session_state.messages
                if m.get("act") == current_act
            ]
            if len(updated_act_messages) >= (WINDOW_ROUNDS * 2):
                with st.spinner("一幕の記憶を要約アーカイブへ記録中..."):
                    new_summary = summarize_old_context(updated_act_messages)
                    st.session_state.summaries.append(new_summary)

            commit_save_data(
                st.session_state.summaries, st.session_state.messages
            )
            st.rerun()
