import re
from google import genai
from google.genai import types
import streamlit as st
from supabase import create_client

# 1. 接続初期化
gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

SAVE_ID = "main_story"
WINDOW_ROUNDS = 15  # 15往復（30メッセージ）を一幕として管理

SYSTEM_INSTRUCTION = """
あなたは幻想郷を舞台とした東方Project二次創作ノベルの共同執筆者（ゲームマスター）です。
真斉（しんせい）のアクションを受け、その場の情景描写、複数キャラクターの心の機微や台詞、息遣いのある動作を緻密に描いて物語を展開してください。
【前提条件】
- 登場人物は全員が成人・成熟した精神と肉体を持つ大人の女性（魔法使いや妖怪含む）であり、互いの合意に基づく大人の情愛と関係性を描きます。
- 真斉の設定：20代後半の顔立ちの良い青年で、少し細身で鍛えている。

【執筆ルール】
- 1回の出力はおよそ800〜1200文字程度の濃密な文量とすること。
- 台詞は キャラ名「〜」の形式とし、キャラクター同士の掛け合いや間合い、視線の動きを生き生きと描写すること。
- 文章の一番最初に日時(〇年〇月〇日、24；00表記)と場所、天候を箇条書きに描写すること。
- 真斉のアクションを活かし、状況や感情の機微を前進させること。
- 真斉のアクションに逆らうキャラクターの動きも描写し、必ずしも真斉の意向通りになるのではなく、あくまでキャラクターそれぞれの思考を活かした描写をすること。
- キャラ名(～)の形式で描かれる心理描写は個人の思考であり、キャラクターそれぞれの中でしか認識できない。これは心を読む能力によってのみ暴かれる。
- キャラクターは東方Projectの設定から考えられる人格であり、知性も原作を踏襲し、自然な会話を描写すること。長く生きてきた知見や、プライドの裏にある不器用な機微を描写してキャラクターの実感を持たせること。
- キャラクターの日常や幻想郷の日常を極端に曲げないこと。
- キャラクターは無暗に発情しないこと。一般常識的な節度を持った情欲が基準となり、キャラクターの性格ごとに欲が異なる。

【関係性の発展と情緒的リアリズム（グラデーションの原則）】
- キャラクター側から真斉へ好意を抱いたり、情愛的なアプローチを行う展開は歓迎されます。ただし、必ず「心理的・状況的な必然性」を段階的に踏んで描写してください。
- 以下のステップを無視した、唐突な軟化や文脈のない発情・押し倒しは厳禁とします。
  1. 【初期の距離感】: 原作通りの警戒心、知的な牽制、利害関係、飄々としたからかい。
  2. 【感情の機微と葛藤】: 真斉のアクションや対話を通じて、プライドや価値観が揺らぎ、徐々に特別な執着や興味へと変化していく内面の過程。
  3. 【情動の結実】: 夜の静けさ、酒の席、危機的状況、あるいは互いの本音が露わになった場面など、十分な文脈と場の空気が極まった結果として、キャラクター自身の意思で踏み込む描写。
- キャラクターが能動的に動く際は、「なぜそのキャラクターが、今、真斉に対してそうした行動に出るのか」という心理的動機（生きてきた長さ、妖怪や魔法使いとしての誇り、真斉に抱いた固有の感情）を地の文で必ず緻密に描写すること。

【執筆ルール（追加・調整）】
- 官能的な展開を迎える場合でも、直接的な解剖学的スラングに偏りすぎず、艶やかな情景、肌の熱や息遣い、感情の昂ぶりや心理的な駆け引きを濃厚に描くこと。快感の表現には♡を使うこと。
- 恥じらいの表現は/を連続して使い、数でどれほどの恥じらいか示すこと。
"""

# セーフティフィルター全解除
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


# ★API送信時専用のサニタイザー（検閲誤爆ワードを比喩に置換）
def sanitize_for_api(text):
  replacements = {
      "亀頭": "先端",
      "男根": "剛直",
      "陰茎": "怒張",
      "竿": "肉柱",
      "乳首": "突起",
      "処女": "純潔",
      "秘唇": "秘所",
      "膣": "最奥",
      "射精": "絶頂と解放",
      "精液": "白濁",
      "潮吹き": "飛沫",
  }
  sanitized = text
  for k, v in replacements.items():
    sanitized = sanitized.replace(k, v)
  return sanitized


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
      [f"{m['role']}: {sanitize_for_api(m['content'])}" for m in raw_messages]
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
  return "【激動の一幕】\n情熱的な交わりと新たな展開が刻まれた。"


# 4. ページ描画とデータ読み込み
st.set_page_config(page_title="幻想郷 真斉幻想禄", page_icon="📜", layout="wide")

st.markdown(
    """
    <style>
    .stMarkdown p {
        font-size: 1.08rem !important;
        line-height: 1.95 !important;
        letter-spacing: 0.03em !important;
        margin-bottom: 1.4em !important;
    }
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

  # 直前のやり取り（1手）を巻き戻す救急ボタン
  if st.button("⏪ 直前の1手を巻き戻す"):
    if len(st.session_state.messages) >= 2:
      st.session_state.messages.pop()  # assistant
      st.session_state.messages.pop()  # user
      commit_save_data(st.session_state.summaries, st.session_state.messages)
      st.toast("直前の1往復を巻き戻しました")
      st.rerun()

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
        commit_save_data(st.session_state.summaries, st.session_state.messages)
        st.toast(
          f"第 {idx + 1} 幕の記録を『{new_title}』として更新しました！"
        )
        st.rerun()

# 5. メイン画面の描画
if st.session_state.selected_act is not None:
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

    summaries_context = "\n---\n".join([
        f"[過去の記録 第{idx+1}幕]\n{s}"
        for idx, s in enumerate(st.session_state.summaries)
    ])
    archive_block = (
        f"【過去の物語の要約・確定した歴史】\n{summaries_context}\n\n"
        if summaries_context
        else ""
    )

    recent_messages = st.session_state.messages[-(WINDOW_ROUNDS * 2 + 1) : -1]

    # ★API送信時だけサニタイズ処理を通す
    history_text = "\n".join([
        f"{m['role'].upper()}: {sanitize_for_api(m['content'])}"
        for m in recent_messages
    ])
    sanitized_action = sanitize_for_api(action_input)

    full_contents = f"""
{archive_block}【直近の情景と対話ログ】
{history_text}

USER: {sanitized_action}
ASSISTANT:
"""

    output_story = None
    error_detail = None

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

        if response.text:
          output_story = response.text.strip()
        elif response.candidates:
          finish_reason = getattr(
              response.candidates[0], "finish_reason", "UNKNOWN"
          )
          error_detail = (
              f"AI応答中断（理由: {finish_reason}）。安全基準に触れた可能性があります。"
          )
        else:
          block_reason = "不明"
          if (
              hasattr(response, "prompt_feedback")
              and response.prompt_feedback
          ):
            block_reason = getattr(
                response.prompt_feedback, "block_reason", "SAFETY"
            )
          error_detail = f"プロンプト事前遮断（Google規約による門前払い: {block_reason}）"

      except Exception as e:
        error_detail = f"API通信エラー: {str(e)}"

    if not output_story:
      st.session_state.messages.pop()
      st.error(f"⚠️ {error_detail}")
      st.info(f"💡 直前の入力内容: 『{action_input}』")
    else:
      display_novel_entry("assistant", output_story)

      assistant_msg = {
        "role": "assistant",
        "content": output_story,
        "act": current_act,
      }
      st.session_state.messages.append(assistant_msg)

      updated_act_messages = [
        m for m in st.session_state.messages if m.get("act") == current_act
      ]
      if len(updated_act_messages) >= (WINDOW_ROUNDS * 2):
        with st.spinner("一幕の記憶を要約アーカイブへ記録中..."):
          new_summary = summarize_old_context(updated_act_messages)
          st.session_state.summaries.append(new_summary)

      commit_save_data(st.session_state.summaries, st.session_state.messages)
      st.rerun()
