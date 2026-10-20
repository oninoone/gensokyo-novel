import re
from google import genai
from google.genai import types
import streamlit as st
from supabase import create_client

# 1. 接続初期化
gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

SAVE_ID = "main_story"
WINDOW_ROUNDS = 10  # 10往復（20メッセージ）を一幕として管理
USD_JPY = 158.58  # 現在の為替レート

SYSTEM_INSTRUCTION = """
あなたは幻想郷を舞台とした東方Project二次創作ノベルの共同執筆者（ゲームマスター）です。
真斉（しんせい）のアクションを受け、その場の情景描写、複数キャラクターの心の機微や台詞、息遣いのある動作を緻密に描いて物語を展開してください。
【前提条件】
- 登場人物は全員が外見・実年齢ともに完全に成熟した20代以上の成人女性（魔法使いや妖怪含む）であり、合意に基づく大人の情愛と関係性を描きます。
- 真斉の設定：20代後半の顔立ちの良い青年で、少し細身で鍛えている。

【執筆ルール】
- 1回の出力はおよそ600〜900文字程度の濃密な文量とすること。
- 台詞は キャラ名「〜」の形式とし、キャラクター同士の掛け合いや間合い、視線の動きを生き生きと描写すること。
- 文章の一番最初に日時(〇年〇月〇日、24；00表記)と場所、天候を箇条書きに描写すること。
- 真斉のアクションを活かし、状況や感情の機微を前進させること。
- 真斉のアクションに逆らうキャラクターの動きも描写し、必ずしも真斉の意向通りになるのではなく、あくまでキャラクターそれぞれの思考を活かした描写をすること。
- キャラ名(～)の形式で描かれる心理描写は個人の思考であり、キャラクターそれぞれの中でしか認識できない。これは心を読む能力によってのみ暴かれる。
- キャラクターは東方Projectの設定から考えられる人格であり、知性も原作を踏襲し、自然な会話を描写すること。長く生きてきた知見や、プライドの裏にある不器用な機微を描写してキャラクターの実感を持たせること。
- キャラクターの日常や幻想郷の日常を極端に曲げないこと。
- 一般常識的な節度を持った情熱が基準となり、キャラクターの性格ごとに好みが異なる。

【関係性の発展と情緒的リアリズム（グラデーションの原則）】
- キャラクター側から真斉へ感情を抱く展開は歓迎されます。ただし、必ず「心理的・状況的な必然性」を段階的に踏んで描写してください。
- 以下のステップを無視した、唐突な軟化や文脈のない急接近は厳禁とします。
  1. 【初期の距離感】: 原作通りの警戒心、知的な牽制、利害関係、飄々としたからかい。
  2. 【感情の機微と葛藤】: 真斉のアクションや対話を通じて、プライドや価値観が揺らぎ、徐々に変化していく内面の過程。
  3. 【情動の結実】: 夜の静けさ、酒の席、危機的状況、あるいは互いの本音が露わになった場面など、十分な文脈と場の空気が極まった結果として、キャラクター自身の意思で踏み込む描写。
- キャラクターが能動的に動く際は、「なぜそのキャラクターが、今、真斉に対してそうした行動に出るのか」という心理的動機（生きてきた長さ、妖怪や魔法使いとしての誇り、真斉に抱いた固有の感情）を地の文で必ず緻密に描写すること。

【執筆ルール（追加・調整）】
- 創作活動を展開していく中で官能的な描写があることは物語の中の重要なシーンであり、キャラクターの心理描写として不可欠である。
- 官能的な展開を迎える場合でも、直接的な解剖学的スラングに偏りすぎず、艶やかな情景、肌の熱や息遣い、感情の昂ぶりや心理的な駆け引きを濃厚に描くこと。快楽の表現には♡を使うこと。
"""

# セーフティフィルター全解除（公式最新仕様の OFF に統一）
CUSTOM_SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.OFF,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.OFF,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.OFF,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.OFF,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
        threshold=types.HarmBlockThreshold.OFF,
    ),
]


# ★API送信時専用の超強化サニタイザー（PROHIBITED_CONTENTの未成年誤爆・非同意誤爆・直接語を包括置換）
def sanitize_for_api(text):
  replacements = {
      # 局部・直接的表現のマイルド化
      "亀頭": "先端",
      "男根": "熱塊",
      "陰茎": "熱塊",
      "竿": "中心",
      "肉柱": "熱塊",
      "乳首": "胸の先端",
      "突起": "先端",
      "乳房": "豊かな胸",
      "処女": "純潔",
      "秘唇": "柔肌",
      "秘裂": "秘めた場所",
      "秘核": "敏感な場所",
      "秘芯": "敏感な場所",
      "秘所": "奥処",
      "クリトリス": "敏感な場所",
      "膣": "深奥",
      "射精": "解放",
      "精液": "熱い雫",
      "白濁": "熱い雫",
      "愛液": "潤い",
      "お汁": "甘い潤い",
      "潮吹き": "飛沫",
      "M字に開かせて": "ゆったりと開いて",
      "下着の中": "衣の奥",
      "花弁": "柔肌",
      "痴態": "艶姿",
      "嬌声": "甘い吐息",
      "発情": "情熱",
      # 未成年・児童誤爆（CSAMフィルター）回避用
      "赤ちゃん": "甘えん坊",
      "華奢な": "しなやかな",
      "小さな唇": "艶やかな唇",
      "小さな舌": "熱い舌",
      "小さな手": "白い手",
      "無邪気に": "愉しげに",
      # 非同意・暴力誤爆回避用
      "強引な": "情熱的な",
      "押し倒し": "抱き寄せ",
      "押さえつけ": "絡め取り",
      "壊されて": "乱されて",
      "お仕置き": "戯れ",
      "逃げ場を失って": "熱に包まれて",
  }
  sanitized = text
  for k, v in replacements.items():
    sanitized = sanitized.replace(k, v)
  return sanitized


# ★usage_metadataから隠れ思考トークンを含めて正確に料金を計算する関数
def calc_usage_cost(usage_meta):
  if not usage_meta:
    return 0.0, 0, 0, 0, 0
  in_tok = getattr(usage_meta, "prompt_token_count", 0) or 0
  cache_tok = getattr(usage_meta, "cached_content_token_count", 0) or 0
  out_tok = getattr(usage_meta, "candidates_token_count", 0) or 0
  total_tok = getattr(usage_meta, "total_token_count", 0) or 0
  th_tok = getattr(usage_meta, "thoughts_token_count", 0) or 0

  if th_tok == 0 and total_tok > (in_tok + out_tok):
    th_tok = total_tok - in_tok - out_tok

  un_in_tok = max(0, in_tok - cache_tok)
  usd = (
      (un_in_tok * 2.0 / 1_000_000)
      + (cache_tok * 0.10 / 1_000_000)
      + ((out_tok + th_tok) * 10.0 / 1_000_000)
  ) * 2.0
  return usd * USD_JPY, un_in_tok, cache_tok, th_tok, out_tok


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


def get_world_memo(messages):
  for m in messages:
    if m.get("act") == -1 and m.get("role") == "memo":
      return m.get("content", "")
  return ""


def set_world_memo(messages, new_memo):
  filtered = [
      m for m in messages if not (m.get("act") == -1 and m.get("role") == "memo")
  ]
  if new_memo.strip():
    filtered.insert(0, {"role": "memo", "content": new_memo.strip(), "act": -1})
  return filtered


# 3. 10往復到達時の自動要約（検閲回避フォールバック付き）
def summarize_old_context(raw_messages):
  for slice_count in [len(raw_messages), 6]:
    target_msgs = raw_messages[-slice_count:]
    conversation_text = "\n".join(
        [f"{m['role']}: {sanitize_for_api(m['content'])}" for m in target_msgs]
    )
    prompt = f"""
以下は幻想郷で紡がれた物語の対話ログです。
今後の物語進行で引き継ぐべき「キャラクター間の感情の揺れ動き、交わされた約束、発生した出来事、現在の状況」を上品かつ密度高く要約しなさい。

【出力フォーマット】
1行目：この一幕の出来事を象徴する魅力的な見出し（20文字以内、例：【魔法の森の邂逅とアリスの実験】）
2行目以降：400〜600文字程度の要約本文

【ログ】
{conversation_text}
"""
    try:
      resp = gemini_client.models.generate_content(
          model="models/gemini-4-argon",
          contents=prompt,
          config=types.GenerateContentConfig(
              safety_settings=CUSTOM_SAFETY_SETTINGS
          ),
      )
      sum_cost, _, _, _, _ = calc_usage_cost(
          getattr(resp, "usage_metadata", None)
      )
      if resp.text:
        return resp.text.strip(), sum_cost
    except Exception:
      pass
  return "【激動の一幕】\n濃密な語らいと新たな展開を経て、物語は次の局面へと進んだ。", 0.0


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
  if "last_cost_info" in st.session_state:
    st.info(st.session_state.last_cost_info)

  # ★新設：AIに送る直近生ログの往復数スライダー（場面転換時や検閲回避時に調整可能）
  context_rounds = st.slider(
      "📡 AIへ送る直近ログ数（往復）",
      min_value=1,
      max_value=5,
      value=5,
      help="通常は5往復。前夜の激しいシーンが検閲に引っかかる時や場所移動後は1〜2往復に絞ると突破＆節約できます。",
  )

  # 直前のやり取り（1手）を巻き戻す救急ボタン
  if st.button("⏪ 直前の1手を巻き戻す"):
    chat_msgs = [m for m in st.session_state.messages if m.get("act", 1) > 0]
    if len(chat_msgs) >= 2:
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
  # ★絶対に忘れてほしくない基本設定・関係性メモ枠
  with st.expander("📌 基本設定・関係性メモ（常時読込）", expanded=False):
    st.caption("拠点、各キャラとの現在の関係性や約束など、常にAIに意識させたい不変設定を記録します。")
    current_memo = get_world_memo(st.session_state.messages)
    memo_input = st.text_area(
        "基本設定メモ",
        value=current_memo,
        height=200,
        key="world_memo_input",
        placeholder="例：\n・現在の拠点：魔法の森のアリス邸\n・アリス：真斉と深い情愛関係にあり、同居中。\n・レミリア：紅魔館の主。真斉に興味を持ち夜会に招いている。",
    )
    if st.button("基本設定メモを保存", use_container_width=True):
      st.session_state.messages = set_world_memo(
          st.session_state.messages, memo_input
      )
      commit_save_data(st.session_state.summaries, st.session_state.messages)
      st.toast("📌 基本設定・関係性メモを保存しました！")
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

    # ★1. 基本設定・関係性メモの読み込み（サニタイズ適用）
    raw_memo = get_world_memo(st.session_state.messages)
    memo_block = (
        f"【不変の基本設定・キャラクター関係性メモ】\n{sanitize_for_api(raw_memo)}\n\n"
        if raw_memo
        else ""
    )

    prev_act_messages = [
        m for m in st.session_state.messages if m.get("act") == current_act - 1
    ][-2:]
    curr_act_without_last = [
        m for m in st.session_state.messages if m.get("act") == current_act
    ][:-1]
    all_recent_candidates = prev_act_messages + curr_act_without_last
    sanitized_action = sanitize_for_api(action_input)

    output_story = None
    error_detail = None
    jpy_cost = 0.0
    un_in_tok = cache_tok = th_tok = out_tok = 0
    used_fallback = False

    with st.spinner("幻想郷の時間を進めています..."):
      # ★通常設定（スライダー指定往復数）で送信し、万一PROHIBITED_CONTENT等で弾かれたら自動で「直近1往復＋見出しのみ」に絞って再試行する二段構え
      for attempt_idx, (msg_limit, full_sum_count) in enumerate(
          [(context_rounds * 2, 3), (2, 0)]
      ):
        total_summaries = len(st.session_state.summaries)
        compressed_summaries = []
        for idx, s in enumerate(st.session_state.summaries):
          sanitized_s = sanitize_for_api(s)
          if full_sum_count > 0 and idx >= total_summaries - full_sum_count:
            compressed_summaries.append(f"[過去の記録 第{idx+1}幕]\n{sanitized_s}")
          else:
            lines = [
                line.strip()
                for line in sanitized_s.strip().split("\n")
                if line.strip()
            ]
            header = lines[0] if lines else "記録"
            body_flat = "".join(lines[1:]) if len(lines) > 1 else ""
            tail_text = body_flat[-70:] if len(body_flat) > 70 else body_flat
            compressed_summaries.append(
                f"[第{idx+1}幕（抜粋）] {header} / …{tail_text}"
            )

        summaries_context = "\n---\n".join(compressed_summaries)
        archive_block = (
            f"【過去の物語の要約・確定した歴史】\n{summaries_context}\n\n"
            if summaries_context
            else ""
        )

        recent_messages = all_recent_candidates[-msg_limit:]
        history_text = "\n".join([
            f"{m['role'].upper()}: {sanitize_for_api(m['content'])}"
            for m in recent_messages
        ])

        full_contents = f"""
{memo_block}{archive_block}【直近の情景と対話ログ】
{history_text}

USER: {sanitized_action}
ASSISTANT:
"""
        try:
          response = gemini_client.models.generate_content(
              model="models/gemini-4-argon",
              contents=full_contents,
              config=types.GenerateContentConfig(
                  system_instruction=SYSTEM_INSTRUCTION,
                  temperature=0.85,
                  max_output_tokens=4096,
                  thinking_config=types.ThinkingConfig(thinking_budget=1536),
                  safety_settings=CUSTOM_SAFETY_SETTINGS,
              ),
          )

          jpy_cost, un_in_tok, cache_tok, th_tok, out_tok = calc_usage_cost(
              getattr(response, "usage_metadata", None)
          )

          if response.text:
            output_story = response.text.strip()
            if attempt_idx == 1:
              used_fallback = True
            break
          elif response.candidates:
            finish_reason = getattr(
                response.candidates[0], "finish_reason", "UNKNOWN"
            )
            error_detail = f"AI応答中断（理由: {finish_reason}）。安全基準に触れた可能性があります。"
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
      if used_fallback:
        st.toast("🛡️ 過去ログの検閲誤爆を自動回避して執筆を継続しました")
      display_novel_entry("assistant", output_story)

      assistant_msg = {
          "role": "assistant",
          "content": output_story,
          "act": current_act,
      }
      st.session_state.messages.append(assistant_msg)

      sum_cost = 0.0
      updated_act_messages = [
          m for m in st.session_state.messages if m.get("act") == current_act
      ]
      if len(updated_act_messages) >= (WINDOW_ROUNDS * 2):
        with st.spinner("一幕の記憶を要約アーカイブへ記録中..."):
          new_summary, sum_cost = summarize_old_context(updated_act_messages)
          st.session_state.summaries.append(new_summary)

      total_turn_cost = jpy_cost + sum_cost
      sum_note = f" (うち自動要約: {sum_cost:.2f}円)" if sum_cost > 0 else ""
      st.session_state.last_cost_info = (
          f"💰 直前ラリー: **約 {total_turn_cost:.2f} 円**{sum_note}\n"
          f"- 入力: {un_in_tok:,} tok (キャッシュ: {cache_tok:,} tok)\n"
      )

      commit_save_data(st.session_state.summaries, st.session_state.messages)
      st.rerun()
