import streamlit as st
from google import genai
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
- 台詞は【キャラ名】「〜」の形式とし、キャラクター同士の掛け合いや間合い、視線の動きを生き生きと描写すること。
- 文章の一番最初に日時(〇年〇月〇日、24；00表記)と場所、天候を箇条書きに描写すること。
- 真斉のアクションを活かし、状況や感情の機微を前進させること。
- 真斉のアクションに逆らうキャラクターの動きも描写し、必ずしも真斉の意向通りになるのではなく、あくまでキャラクターそれぞれの思考を活かした描写をすること。
- 官能的な描写や流れを自然に作ること。直接的な性描写も含めること。
- ()で描かれる心理描写は個人の思考であり、キャラクターそれぞれの中でしか認識できない。これは心を読む能力によってのみ暴かれる。
- キャラクターは東方Projectの設定から考えられる人格であり、知性も原作を踏襲し、自然な会話を描写すること。
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
今後の物語進行で引き継ぐべき「キャラクター間の感情の揺れ動き、交わされた約束、発生した出来事、現在の状況」を密度高く要約しなさい。

【出力フォーマット】
1行目：この一幕の出来事を象徴する魅力的な見出し（20文字以内、例：【魔法の森の邂逅とアリスの実験】）
2行目以降：400〜600文字程度の要約本文

【ログ】
{conversation_text}
"""
    resp = gemini_client.models.generate_content(
        model="models/gemini-3.8-flash", contents=prompt
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

# 表示中の幕（Noneなら最新の現在進行中の幕）
if "selected_act" not in st.session_state:
    st.session_state.selected_act = None

with st.sidebar:
    st.title("📜 記憶アーカイブ")

    # 回想中または通常時に使える「現在へ」復帰ボタン
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

    total_rounds = len(st.session_state.messages) // 2
    current_act = len(st.session_state.summaries) + 1
    act_rounds = total_rounds % WINDOW_ROUNDS
    remaining = WINDOW_ROUNDS - act_rounds
    progress_val = act_rounds / WINDOW_ROUNDS

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
            # ★当時の生ログを表示するボタン
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

# 5. メイン画面の描画切り替え
if st.session_state.selected_act is not None:
    # --- 【回想モード】当時の記憶（生ログ）を表示 ---
    act_idx = st.session_state.selected_act
    col_t, col_b = st.columns([4, 1])
    with col_t:
        st.title(f"📖 第 {act_idx + 1} 幕の記憶（回想中）")
    with col_b:
        if st.button("↩ 現在へ", key="back_to_present_main", use_container_width=True):
            st.session_state.selected_act = None
            st.rerun()

    start_idx = act_idx * (WINDOW_ROUNDS * 2)
    end_idx = start_idx + (WINDOW_ROUNDS * 2)
    reminiscence_messages = st.session_state.messages[start_idx:end_idx]

    for msg in reminiscence_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

else:
    # --- 【通常モード】現在進行中の最新のやりとりを表示 ---
    st.title("幻想郷 真斉幻想禄")

    current_start_idx = len(st.session_state.summaries) * (WINDOW_ROUNDS * 2)
    active_messages = st.session_state.messages[current_start_idx:]

    for msg in active_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # アクション入力と生成（現在進行中のみ入力可能）
    if action_input := st.chat_input("真斉のアクションや台詞を入力..."):
        st.session_state.messages.append(
            {"role": "user", "content": action_input}
        )
        with st.chat_message("user"):
            st.markdown(action_input)

        num_summaries = len(st.session_state.summaries)
        target_count = (num_summaries + 1) * (WINDOW_ROUNDS * 2)

        if len(st.session_state.messages) > target_count:
            with st.spinner("一幕の記憶を要約アーカイブへ記録中..."):
                start_idx = num_summaries * (WINDOW_ROUNDS * 2)
                end_idx = target_count
                to_summarize = st.session_state.messages[start_idx:end_idx]
                new_summary = summarize_old_context(to_summarize)
                st.session_state.summaries.append(new_summary)

        # プロンプトの組み立て
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

        with st.chat_message("assistant"):
            with st.spinner("幻想郷の時間を進めています..."):
                response = gemini_client.models.generate_content(
                    model="models/gemini-3.8-flash",
                    contents=full_contents,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.85,
                        max_output_tokens=2048,
                    ),
                )
                output_story = response.text.strip()
                st.markdown(output_story)

        # 全履歴をSupabaseへ永続保存
        st.session_state.messages.append(
            {"role": "assistant", "content": output_story}
        )
        commit_save_data(st.session_state.summaries, st.session_state.messages)
        st.rerun()
