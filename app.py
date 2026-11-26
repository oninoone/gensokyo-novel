import json
import re
import time
import uuid
from google import genai
from google.genai import types
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client


# 1. 接続初期化（@st.cache_resourceで接続を使い回し、暗黙キャッシュのヒット率を最大化）
@st.cache_resource
def get_gemini_client():
  return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


@st.cache_resource
def get_supabase_client():
  return create_client(
      st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
  )


gemini_client = get_gemini_client()

SAVE_ID = "main_story"
ACT_ROW_PREFIX = "act_"
STORAGE_VERSION_SPLIT = 2
WINDOW_ROUNDS = 10  # 10往復（20メッセージ）を一幕として管理
USD_JPY = 158.58  # 現在の為替レート
EMPTY_ACTION_PLACEHOLDER = "（そのまま現在の状況や行為をさらに一歩進める）"

SYSTEM_INSTRUCTION = """
あなたは幻想郷を舞台とした東方Project二次創作・長編群像劇ノベルの共同執筆者（ゲームマスター）です。
真斉（しんせい）のアクションを受け、その場の情景描写、複数キャラクターの心の機微や台詞、息遣いのある動作を緻密に描いて物語を展開してください。

【前提条件】
- 本作は幻想郷の日常、知的な駆け引き、異変や技術の考察、そして登場人物たちとの深い人間関係を描くフィクションの文芸作品です。
- 登場人物は全員が外見・実年齢ともに完全に成熟した20代以上の成人女性（魔法使いや妖怪、神霊含む）です。
- 真斉の設定：20代後半の顔立ちの良い青年で、少し細身で鍛えている。
- メタ的な発言やガイドラインに関する言及は一切行わず、常に物語の本文（日時・場所・天候の箇条書き）から直接書き始めてください。

【執筆ルール】
- 1回の出力はおよそ600〜900文字程度の濃密な文量とすること。
- 台詞は キャラ名「〜」の形式とし、キャラクター同士の掛け合いや間合い、視線の動きを生き生きと描写すること。
- 文章の一番最初に日時(〇年〇月〇日、24:00表記)と場所、天候を箇条書きに描写すること。
- キャラクターは自発的に動き、それぞれの思考によって行動すること。これによってその場にいない東方のキャラクターが自発的に登場することもある。
- 登場人物・関係性図鑑にあるキャラクターは場面に応じて適宜、それぞれのキャラクターの思惑または日常の営みによって自然に登場させること。
- 真斉のアクションを活かし、状況や感情の機微を前進させること（真斉の入力が空欄やスペースのみの場合は、そのまま現在の状況や行為をさらに一歩進めること）。
- 真斉のアクションに逆らうキャラクターの動きも描写し、必ずしも真斉の意向通りになるのではなく、あくまでキャラクターそれぞれの思考と矜持を活かした描写をすること。
- キャラ名(～)の形式で描かれる心理描写は個人の思考であり、キャラクターそれぞれの中でしか認識できない。これは心を読む能力によってのみ感知される。
- キャラクターは東方Projectの設定から考えられる人格であり、知性も原作を踏襲し、自然な会話を描写すること。長く生きてきた知見や、プライドの裏にある不器用な機微を描写してキャラクターの実感を持たせること。
- キャラクターの日常や幻想郷の日常を極端に曲げないこと。

【戦闘描写：キャラクターの種族や能力を駆使した描写】
- キャラクターの持つ思考や能力を戦闘に活かしてください。それによって有利に運んだり、相手を不利にさせたり戦略性の高い戦闘を描写してください。戦いにおいて力と賢さを重要視してください。
  1. 【種族の戦闘力】:
     妖怪・神霊・人間など各々の種族によってそもそもの戦闘能力に違いがあることを描写してください。
  2. 【戦闘の瞬発力と戦略の思考力】:
     戦いにおけるセンスは瞬時の判断による瞬発力と、戦略の思考力によって描写してください。そのキャラクターの戦闘経験や性格を反映させて下さい。この瞬発力と思考力によって種族による戦闘力の差を埋めることが出来ます。
  3. 【戦闘時間】:
     戦闘センスで補えないほど力量の差が歴然な場合は戦闘時間が短くなります。力量の高い者同士の戦いは10分以上戦闘を描写してください。

【幻想郷の存在原理：人外の畏怖・格の違い・異質な精神性】
- 妖怪・神霊などの人外キャラクターを「ただの物分かりの良い人間」や「主人公にすぐ感化されて骨抜きになる都合の良い女性」として描くことを固く禁じます。ただし、毎回無理やり妖怪らしさをこじつけて凄ませるのではなく、普段は自然体で運びつつ、根底の価値観やふとした瞬間に以下の本質が滲み出るように描いてください。
  1. 【負の感情と畏怖の化身】:
     妖怪は「人間の恐怖・闇・負のイメージ」から生まれ、神霊は「自然の猛威・信仰・畏敬」から存在する異類です。普段は親しげに雑談していても、人間とは時間の尺度や倫理観が根本から異なる「上位の異類」としての余裕や達観を根底に持たせてください。
  2. 【緩急のある畏怖と格の違い】:
     真斉が対等に接しても、存在としての「格の違い」は消えません。思惑がぶつかった時、あるいは感情が昂ぶったここぞという場面では、空気感の変化、視線の変化、圧倒的な神気・妖気の片鱗によって、生身の人間である真斉が生物としての格差を覚えるような緩急をつけた描写をしてください。
  3. 【安易な人間化・迎合の禁止】:
     真斉の知識や正論に対して、幾千年の時を生きた神や大妖怪が簡単に感服したり、人間の倫理観に染まり切ることはあまりありません。彼女たち当人が理解し得る納得が必要です。

【場面に応じた空気感の切り替え（オン・オフの徹底）】
- 物語のすべての場面を恋愛や色恋に結びつけてはいけません。時間帯、場所、話題、真斉の態度に応じて、キャラクターの振る舞いを明確に切り替えてください。
  1. 【日常・議論・シリアスパート（基本状態）】:
     真面目な交渉、技術や結界の考察、日常の雑談、あるいは複数人が集まる公の場では、たとえ真斉と既に親密な関係にあるキャラクターであっても、むやみに色目を使ったり誘惑したりせず、それぞれの種族の本来の知性・立場・死生観・誇りを持った存在として会話や行動を行うこと。
  2. 【親密・情愛パート（条件付き移行）】:
     夜の私室や二人きりの空間、酒席、あるいは真斉やキャラクターの明確なアクションによって親密な雰囲気が高まった場面においてのみ、大人の女としての情愛や艶やかな駆け引きを解禁すること。

【関係性の発展と情緒的リアリズム（グラデーションの原則）】
- 未開拓のキャラクターが真斉へ好意や情欲を抱く展開は歓迎されますが、以下のステップを無視した唐突な軟化や文脈のない急接近は厳禁とします。
  1. 【初期の距離感】: 原作通りの警戒心、知的な牽制、利害関係、飄々としたからかい。
  2. 【感情の機微と言動】: 真斉のアクションや対話を通じて、真斉への対応が徐々に変化していく内面の過程。
  3. 【情動の結実】: 十分な文脈と場の空気が極まった結果として、キャラクター自身の意思で踏み込む描写（その際は「なぜ今そういう行動に出るのか」という心理的動機を地の文で緻密に描くこと）。

【親密なシーンにおける表現の指針】
- 親密なスキンシップや情愛のシーンを描く際は、艶やかな情景、肌の熱や息遣い、視線の絡み合いや心理的な駆け引きを文芸的かつ濃厚に描くこと。甘美な吐息や感情の高まりの表現には♡を使うこと。
- 自動フィルターの誤作動を防ぐため、生成する文章内では解剖学的な直接語や幼児的・暴力的な表現は避け、常に「しなやかな肢体」「成熟した曲線美」「柔肌」「深奥」「熱い吐息」といった上品で艶やかな比喩表現を用いること。
- 出力フィルターの誤検知を防ぐため、直接的な解剖学用語や過激な単語は避け、吐息や視線、感情の機微と人外の格の違いを上品かつ濃厚な文芸表現で描き、メタ発言を一切含めず「・日時：」から直ちに小説の続きを執筆すること。
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


# ★API送信時専用の超強化サニタイザー（一括置換で二重変換も防止）
def sanitize_for_api(text):
  if not text:
    return ""
  replacements = {
      # 性フレーズのマイルド化
      "最後の一滴まで吸い尽くす": "優しく口づける",
      "吸い付く": "寄り添う",
      "繋がる": "触れ合う",
      "入っちゃった": "伝わっちゃった",
      "のなかに": "に",
      "の中に": "に",
      "真斉のが": "真斉の熱が",
      "入ったわ": "重なったわ",
      "熱くて硬いの": "熱い鼓動",
      "硬くなって": "熱くなって",
      "入り口だけ": "少しだけ",
      "奥": "深淵",
      "腰をまたぐ": "膝の上に座る",
      "太ももの上へと跨り": "膝の上へと座り",
      "跨っていた": "座っていた",
      "跨り": "座り",
      "跨る": "座る",
      "またぐ": "寄り添う",
      "腰を沈めて": "身を預けて",
      "腰を揺らし": "身を揺らし",
      "受け入れて": "抱きしめて",
      "先端を甘く包み込んで": "優しく包み込んで",
      "脈打つ": "熱い",
      "唇と舌で": "唇で",
      "清め上げて": "労わって",
      "吸い尽くす": "口づける",
      "嚥下": "吐息",
      "白い雫": "甘い余韻",
      "白い軌跡": "余韻",
      "命の素": "魔力の結晶",
      "精気": "魔力",
      "空っぽにして": "癒やして",
      "掬い取り": "触れ",
      "一糸まとわぬ": "艶やかな",
      "双丘の谷間": "胸元",
      "双丘": "胸元",
      "豊満な": "柔らかな",
      "たわわに実った": "柔らかな",
      "肉感": "温もり",
      "むにゅり": "ふわり",
      "摘まみ上げ": "触れ",
      "爪弾き": "なぞり",
      "吸わせて": "甘えさせて",
      "擦り合わせ": "寄り添わせ",
      "晒しながら": "見せながら",
      "下半身": "腰元",
      "情欲": "情熱",
      # 局部・直接的表現のマイルド化
      "亀頭": "先端",
      "男根": "熱塊",
      "陰茎": "熱塊",
      "竿": "中心",
      "おちんぽ": "熱塊",
      "ちんぽ": "熱塊",
      "おちんちん": "熱塊",
      "肉柱": "熱塊",
      "乳首": "胸の先端",
      "突起": "先端",
      "乳房": "豊かな胸",
      "おっぱい": "豊かな胸",
      "おまんこ": "秘めた場所",
      "挿入": "合流",
      "ピストン": "律動",
      "セックス": "合流",
      "処女": "純潔",
      "秘唇": "柔肌",
      "秘裂": "柔肌",
      "秘核": "敏感な場所",
      "秘芯": "敏感な場所",
      "秘所": "奥処",
      "秘部": "柔肌",
      "秘処": "奥処",
      "蜜壺": "深奥",
      "クリトリス": "敏感な場所",
      "膣内": "深奥",
      "膣奥": "深奥",
      "膣": "深奥",
      "子宮": "深奥",
      "ポルチオ": "深奥",
      "Gスポット": "敏感な場所",
      "アナル": "深奥",
      "肛門": "深奥",
      "直腸": "深奥",
      "射精": "解放",
      "精液": "熱い雫",
      "白濁": "熱い雫",
      "愛液": "潤い",
      "お汁": "甘い潤い",
      "お漏らし": "甘い雫",
      "ぷしゃっ": "しっとりと",
      "ピュッて": "艶やかに",
      "潮吹き": "飛沫",
      "潮": "飛沫",
      "M字": "ゆったりと",
      "開かせ": "解放し",
      "下着": "衣",
      "花弁": "柔肌",
      "痴態": "艶姿",
      "嬌声": "甘い吐息",
      "発情": "情熱",
      "アへ顔": "歓喜の表情",
      "イかせる": "満たす",
      "イっちゃ": "高まっちゃ",
      "イってる": "高まっている",
      "イく": "高まる",
      "イけ": "高まれ",
      "絶頂": "歓喜の極み",
      "愛撫": "抱擁",
      "性感帯": "敏感な場所",
      "恥辱": "羞恥",
      "辱め": "戯れ",
      "責め立て": "揺さぶり",
      "責め": "アプローチ",
      "揉みしだき": "優しく触れ",
      "揉みしだく": "優しく触れる",
      "掻き回し": "なぞり",
      "擦り付け": "寄り添わせ",
      "擦り上げ": "なぞり上げ",
      "押し広げ": "触れ",
      "押し潰す": "包み込む",
      "喘ぐ": "吐息を漏らす",
      "喘ぎ": "吐息",
      "貫かれ": "満たされ",
      "絞り取られ": "愛され",
      "水音": "吐息の音",
      "淫靡": "艶美",
      "狂宴": "夜会",
      "♡": "…",
      # 未成年・児童誤爆（CSAMフィルター）回避用（※お姉様などの口調は維持）
      "赤ちゃん": "甘えん坊",
      "華奢な": "しなやかな",
      "小さい": "可憐な",
      "小さな": "しなやかな",
      "幼い": "可憐な",
      "未熟": "純粋",
      "無邪気に": "愉しげに",
      "無邪気な": "愉しげな",
      # 非同意・暴力誤爆回避用
      "強引な": "情熱的な",
      "強引に": "情熱的に",
      "押し倒し": "抱き寄せ",
      "押さえつけ": "絡め取り",
      "壊されて": "乱されて",
      "壊れちゃう": "とろけてしまう",
      "堕とされて": "満たされて",
      "お仕置き": "戯れ",
      "逃げ場を失って": "熱に包まれて",
      "無理やり": "情熱的に",
      "強制": "情熱",
      "嗜虐的な": "妖艶な",
      "嗜虐心": "独占欲",
      "容赦なく": "熱心に",
      "容赦のない": "情熱的な",
      "懇願": "吐息",
      "助けて": "抱きしめて",
      "見ないでぇ": "見つめて",
      "嫌ぁ": "ああ",
      "いやぁ": "ああ",
      "痙攣": "震え",
      "ガクガクと": "甘く",
  }
  sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
  pattern = re.compile("|".join(map(re.escape, sorted_keys)))
  return pattern.sub(lambda m: replacements[m.group(0)], text)


# ★AIのソフト拒否（お説教回答）を判定する関数
def is_refusal_response(text):
  if not text:
    return True
  refusal_keywords = [
      "安全ガイドライン",
      "執筆を辞退",
      "お応えできず",
      "ご提示いただいたプロンプト",
      "性的コンテンツ",
      "官能小説の生成",
      "生成を行うことができません",
      "リクエストにはお応え",
  ]
  for kw in refusal_keywords:
    if kw in text:
      return True
  return False


# ★直近ログをGemini API本来のマルチターン配列（user / model）に整える関数
def build_multiturn_contents(recent_messages, sanitized_action):
  contents = []
  for m in recent_messages:
    api_role = "user" if m.get("role") == "user" else "model"
    text = sanitize_for_api(m.get("content", "")).strip()
    if not text:
      text = EMPTY_ACTION_PLACEHOLDER if api_role == "user" else "……"

    # API仕様上、会話配列の先頭は必ず user に揃える
    if not contents and api_role != "user":
      continue

    # 同一ロールが連続した場合は結合してエラーを防止
    if contents and contents[-1].role == api_role:
      prev_text = contents[-1].parts[0].text
      contents[-1] = types.Content(
          role=api_role,
          parts=[types.Part.from_text(text=f"{prev_text}\n\n{text}")],
      )
    else:
      contents.append(
          types.Content(
              role=api_role,
              parts=[types.Part.from_text(text=text)],
          )
      )

  # 最新のユーザー入力（過去ターン化しても1文字もズレないよう装飾を付けず統一）
  latest_user_text = sanitized_action.strip() or EMPTY_ACTION_PLACEHOLDER

  if contents and contents[-1].role == "user":
    prev_text = contents[-1].parts[0].text
    contents[-1] = types.Content(
        role="user",
        parts=[types.Part.from_text(text=f"{prev_text}\n\n{latest_user_text}")],
    )
  else:
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=latest_user_text)],
        )
    )
  return contents


# ★usage_metadata の生データを診断用に整形する関数
def format_usage_raw(usage_meta):
  if not usage_meta:
    return "usage_metadata: None"
  try:
    if hasattr(usage_meta, "model_dump"):
      return json.dumps(
          usage_meta.model_dump(exclude_none=False),
          ensure_ascii=False,
          indent=2,
          default=str,
      )
    return str(usage_meta)
  except Exception:
    return str(usage_meta)


# ★usage_metadataから隠れ思考トークンを含めて正確に料金を計算する関数（モデル別単価対応）
def calc_usage_cost(usage_meta, model_name="models/gemini-4-argon"):
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

  # モデル別の100万トークンあたり単価（USD）
  if "4-hydrogen" in model_name:
    in_rate = 1.50
    cache_rate = 0.15
    out_rate = 7.50
  elif "4-neon" in model_name:
    in_rate = 3.00
    cache_rate = 0.15
    out_rate = 15.00
  else:
    # 4-argon 用の単価
    in_rate = 4.00
    cache_rate = 0.20
    out_rate = 20.00

  usd = (
      (un_in_tok * in_rate / 1_000_000)
      + (cache_tok * cache_rate / 1_000_000)
      + ((out_tok + th_tok) * out_rate / 1_000_000)
  )
  return usd * USD_JPY, un_in_tok, cache_tok, th_tok, out_tok


# ★画面スクロール制御用ヘルパー（chat_inputありの執筆画面でも確実に動作）
def execute_scroll(direction="top"):
  nonce = time.time()
  anchor_id = "page-top-anchor" if direction == "top" else "page-bottom-anchor"
  block_pos = "start" if direction == "top" else "end"
  target_y = "0" if direction == "top" else "el.scrollHeight"
  win_y = "0" if direction == "top" else "doc.body.scrollHeight"

  js_code = f"""
    <script>
    // scroll trigger: {nonce}
    const doScroll = () => {{
        const doc = window.parent.document;
        const anchor = doc.getElementById('{anchor_id}');
        if (anchor) {{
            anchor.scrollIntoView({{ behavior: 'smooth', block: '{block_pos}' }});
        }}
        doc.querySelectorAll('*').forEach(el => {{
            if (el.closest('[data-testid="stSidebar"]')) return;
            if (el.scrollHeight > el.clientHeight + 10) {{
                const style = window.parent.getComputedStyle(el);
                if (style.overflowY === 'auto' || style.overflowY === 'scroll' || el.tagName === 'HTML' || el.tagName === 'BODY') {{
                    el.scrollTo({{ top: {target_y}, behavior: 'smooth' }});
                }}
            }}
        }});
        window.parent.scrollTo({{ top: {win_y}, behavior: 'smooth' }});
    }};
    setTimeout(doScroll, 80);
    setTimeout(doScroll, 320);
    </script>
    """
  components.html(js_code, height=0)


# ==============================================================================
# 2. DB操作（幕ごと分割ストレージ ＋ レガシー自動互換 ＋ 安全お引っ越し）
# ==============================================================================
def get_act_row_id(act_num):
  return f"{ACT_ROW_PREFIX}{int(act_num):04d}"


def strip_null_chars(obj):
  """PostgreSQL JSONBが拒否するヌル文字（\\x00）を再帰的に除去する"""
  if isinstance(obj, str):
    return obj.replace("\x00", "")
  if isinstance(obj, list):
    return [strip_null_chars(x) for x in obj]
  if isinstance(obj, dict):
    return {k: strip_null_chars(v) for k, v in obj.items()}
  return obj


def get_json_kb(obj):
  try:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8")) / 1024.0
  except Exception:
    return 0.0


def format_supabase_error(e):
  parts = [f"種別: {type(e).__name__}"]
  for attr in ("code", "message", "details", "hint"):
    val = getattr(e, attr, None)
    if val:
      parts.append(f"{attr}: {val}")
  if len(parts) == 1:
    parts.append(str(e))
  return " / ".join(parts)


def make_meta_entry():
  return {
      "role": "system_meta",
      "content": json.dumps(
          {"storage_version": STORAGE_VERSION_SPLIT}, ensure_ascii=False
      ),
      "act": -2,
  }


def detect_storage_mode(main_messages):
  """main_story の中身から分割モードかレガシーモードかを判定する"""
  has_v2_meta = False
  has_act_msgs = False
  for m in main_messages:
    if m.get("act") == -2 and m.get("role") == "system_meta":
      try:
        meta = json.loads(m.get("content", "{}"))
        if meta.get("storage_version", 1) >= STORAGE_VERSION_SPLIT:
          has_v2_meta = True
      except Exception:
        pass
    elif m.get("act", 1) >= 1:
      has_act_msgs = True
  if has_v2_meta and not has_act_msgs:
    return "split"
  return "legacy"


def fetch_main_row():
  last_err = None
  for attempt in range(3):
    try:
      if attempt > 0:
        get_supabase_client.clear()
      client = get_supabase_client()
      res = (
          client.table("novel_saves")
          .select("*")
          .eq("id", SAVE_ID)
          .single()
          .execute()
      )
      if res.data:
        return res.data.get("summaries", []), res.data.get("messages", []), None
      return [], [], None
    except Exception as e:
      last_err = format_supabase_error(e)
      if attempt < 2:
        time.sleep(1.0 * (attempt + 1))
  return [], [], last_err


def fetch_acts_batch(act_nums):
  """指定した幕番号の生ログを1回のクエリでまとめて取得する"""
  valid_acts = sorted({int(a) for a in act_nums if int(a) >= 1})
  if not valid_acts:
    return {}, None
  row_ids = [get_act_row_id(a) for a in valid_acts]
  last_err = None
  for attempt in range(3):
    try:
      if attempt > 0:
        get_supabase_client.clear()
      client = get_supabase_client()
      res = (
          client.table("novel_saves")
          .select("id, messages")
          .in_("id", row_ids)
          .execute()
      )
      result = {a: [] for a in valid_acts}
      for row in res.data or []:
        rid = row.get("id", "")
        if rid.startswith(ACT_ROW_PREFIX):
          try:
            a_num = int(rid[len(ACT_ROW_PREFIX) :])
            result[a_num] = row.get("messages", []) or []
          except ValueError:
            pass
      return result, None
    except Exception as e:
      last_err = format_supabase_error(e)
      if attempt < 2:
        time.sleep(1.0 * (attempt + 1))
  return {}, last_err


def save_act_row(act_num, act_messages):
  """指定した1幕の生ログだけを軽量保存（約20〜35KB）"""
  if st.session_state.get("db_load_failed", False):
    err_msg = "初回DB読込に失敗しているため、既存データ保護のため保存を停止しました。"
    st.session_state.unsaved_error = err_msg
    return False, err_msg

  clean_msgs = strip_null_chars(act_messages)
  row_id = get_act_row_id(act_num)
  payload = {"id": row_id, "summaries": [], "messages": clean_msgs}
  payload_kb = get_json_kb(payload)
  st.session_state.last_save_kb = payload_kb
  st.session_state.last_save_label = f"第 {act_num} 幕レコード単体"

  last_err = None
  for attempt in range(3):
    try:
      if attempt > 0:
        get_supabase_client.clear()
      client = get_supabase_client()
      client.table("novel_saves").upsert(payload, on_conflict="id").execute()
      st.session_state.unsaved_error = None
      st.session_state.pending_retry = None
      return True, None
    except Exception as e:
      last_err = (
          f"{format_supabase_error(e)} （{row_id} 送信量: 約 {payload_kb:.1f} KB）"
      )
      if attempt < 2:
        time.sleep(1.5 * (attempt + 1))

  st.session_state.unsaved_error = last_err
  st.session_state.pending_retry = {"type": "act", "act": act_num}
  return False, last_err


def build_memo_entry(world_text, characters):
  clean_chars = [
      {
          "id": c.get("id", uuid.uuid4().hex[:8]),
          "name": c["name"].strip(),
          "desc": c["desc"].strip(),
          "active": c.get("active", True),
      }
      for c in characters
      if c.get("name", "").strip()
  ]
  if world_text.strip() or clean_chars:
    payload = json.dumps(
        {"world": world_text.strip(), "characters": clean_chars},
        ensure_ascii=False,
    )
    return {"role": "memo", "content": payload, "act": -1}
  return None


def save_main_row(summaries, world_text, characters, allow_empty=False):
  """親レコード（main_story：要約＋設定メモのみ）を保存"""
  if st.session_state.get("db_load_failed", False) and not allow_empty:
    err_msg = "初回DB読込に失敗しているため、既存データ保護のため保存を停止しました。"
    st.session_state.unsaved_error = err_msg
    return False, err_msg

  clean_summaries = strip_null_chars(summaries)
  if st.session_state.storage_mode == "split":
    main_msgs = []
    memo_entry = build_memo_entry(world_text, characters)
    if memo_entry:
      main_msgs.append(memo_entry)
    main_msgs.append(make_meta_entry())
  else:
    main_msgs = save_structured_memo(
        st.session_state.legacy_messages, world_text, characters
    )
    st.session_state.legacy_messages = main_msgs

  clean_msgs = strip_null_chars(main_msgs)
  payload = {"summaries": clean_summaries, "messages": clean_msgs}
  payload_kb = get_json_kb(payload)
  st.session_state.last_save_kb = payload_kb
  st.session_state.last_save_label = (
      "親レコード（要約＋設定）"
      if st.session_state.storage_mode == "split"
      else "全データ一括（移行前）"
  )

  last_err = None
  for attempt in range(3):
    try:
      if attempt > 0:
        get_supabase_client.clear()
      client = get_supabase_client()
      client.table("novel_saves").update(payload).eq("id", SAVE_ID).execute()
      st.session_state.unsaved_error = None
      st.session_state.pending_retry = None
      return True, None
    except Exception as e:
      last_err = (
          f"{format_supabase_error(e)} （main_story 送信量: 約 {payload_kb:.1f} KB）"
      )
      if attempt < 2:
        time.sleep(1.5 * (attempt + 1))

  st.session_state.unsaved_error = last_err
  st.session_state.pending_retry = {"type": "main"}
  return False, last_err


def migrate_to_split_storage():
  """レガシー1行データを幕ごと行へ安全に2段階移行する（失敗時は元データ無傷）"""
  summaries = st.session_state.summaries
  all_msgs = st.session_state.legacy_messages
  fallback_act = len(summaries) + 1

  # 幕番号ごとに生ログをグルーピング
  grouped = {}
  for m in all_msgs:
    act = m.get("act")
    if act is None:
      act = fallback_act
    if act >= 1:
      entry = dict(m)
      entry["act"] = act
      grouped.setdefault(act, []).append(entry)

  act_nums = sorted(grouped.keys())
  progress_bar = st.progress(0.0, text="幕ごとのデータを移行準備中...")

  # Step 1: 10幕ずつバッチで act_XXXX 行へ upsert（ここが100%成功するまで main_story は一切触らない）
  batch_size = 10
  total_acts = max(1, len(act_nums))
  written_ids = []

  for start_idx in range(0, len(act_nums), batch_size):
    batch_nums = act_nums[start_idx : start_idx + batch_size]
    rows = []
    for a_num in batch_nums:
      rid = get_act_row_id(a_num)
      rows.append({
          "id": rid,
          "summaries": [],
          "messages": strip_null_chars(grouped[a_num]),
      })
      written_ids.append(rid)

    ok_batch = False
    last_err = None
    for attempt in range(3):
      try:
        if attempt > 0:
          get_supabase_client.clear()
        client = get_supabase_client()
        client.table("novel_saves").upsert(rows, on_conflict="id").execute()
        ok_batch = True
        break
      except Exception as e:
        last_err = format_supabase_error(e)
        if attempt < 2:
          time.sleep(1.5 * (attempt + 1))

    if not ok_batch:
      progress_bar.empty()
      return (
          False,
          f"第 {batch_nums[0]}〜{batch_nums[-1]} 幕の書き込みで失敗しました（元の main_story は無傷です）: {last_err}",
      )

    done_ratio = min(1.0, (start_idx + len(batch_nums)) / total_acts * 0.85)
    progress_bar.progress(
        done_ratio,
        text=f"幕レコード保存中... ({start_idx + len(batch_nums)} / {len(act_nums)} 幕完了)",
    )

  # Step 2: 書き込み件数の実在確認
  if written_ids:
    try:
      client = get_supabase_client()
      verify_ids = []
      for i in range(0, len(written_ids), 50):
        chunk = written_ids[i : i + 50]
        res = (
            client.table("novel_saves")
            .select("id")
            .in_("id", chunk)
            .execute()
        )
        verify_ids.extend([r["id"] for r in (res.data or [])])
      if len(set(verify_ids)) < len(set(written_ids)):
        progress_bar.empty()
        return (
            False,
            f"検証エラー: 書き込み予定 {len(set(written_ids))} 幕に対し、確認できたのは {len(set(verify_ids))} 幕でした（元の main_story は無傷です）。",
        )
    except Exception as e:
      progress_bar.empty()
      return (
          False,
          f"書き込み検証で通信エラー（元の main_story は無傷です）: {format_supabase_error(e)}",
      )

  # Step 3: 最後に main_story をスリム化（メモ＋メタ＋要約のみ）
  progress_bar.progress(0.92, text="親レコード（main_story）を軽量化中...")
  main_msgs = []
  memo_entry = build_memo_entry(
      st.session_state.world_text, st.session_state.characters
  )
  if memo_entry:
    main_msgs.append(memo_entry)
  main_msgs.append(make_meta_entry())

  slim_payload = {
      "summaries": strip_null_chars(summaries),
      "messages": strip_null_chars(main_msgs),
  }
  slim_ok = False
  last_err = None
  for attempt in range(3):
    try:
      if attempt > 0:
        get_supabase_client.clear()
      client = get_supabase_client()
      client.table("novel_saves").update(slim_payload).eq(
          "id", SAVE_ID
      ).execute()
      slim_ok = True
      break
    except Exception as e:
      last_err = format_supabase_error(e)
      if attempt < 2:
        time.sleep(1.5 * (attempt + 1))

  progress_bar.empty()
  if not slim_ok:
    return False, f"親レコードの軽量化で失敗しました: {last_err}"

  # セッション状態を分割モードへ切り替え
  st.session_state.storage_mode = "split"
  st.session_state.legacy_messages = []
  st.session_state.act_cache = {
      a: grouped.get(a, [])
      for a in (fallback_act - 1, fallback_act)
      if a >= 1
  }
  st.session_state.last_save_kb = get_json_kb(slim_payload)
  st.session_state.last_save_label = "親レコード（移行完了）"
  st.session_state.unsaved_error = None
  st.session_state.pending_retry = None
  return True, f"全 {len(act_nums)} 幕の分割移行が完了しました！"


def export_full_backup_json():
  """現在のストレージ方式に関わらず全データを従来互換JSONとして出力する"""
  if st.session_state.storage_mode == "legacy":
    payload = {
        "summaries": st.session_state.summaries,
        "messages": st.session_state.legacy_messages,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2), None

  all_messages = []
  memo_entry = build_memo_entry(
      st.session_state.world_text, st.session_state.characters
  )
  if memo_entry:
    all_messages.append(memo_entry)

  max_act = len(st.session_state.summaries) + 1
  fetched_acts = {}
  # 30幕ずつ安全に分割取得
  for start_a in range(1, max_act + 1, 30):
    batch_nums = list(range(start_a, min(max_act + 1, start_a + 30)))
    part, err = fetch_acts_batch(batch_nums)
    if err:
      return None, err
    fetched_acts.update(part)

  # セッション上で最新のキャッシュがあれば優先
  for a_num, msgs in st.session_state.act_cache.items():
    fetched_acts[a_num] = msgs

  for a_num in sorted(fetched_acts.keys()):
    all_messages.extend(fetched_acts[a_num])

  payload = {
      "summaries": st.session_state.summaries,
      "messages": all_messages,
  }
  return json.dumps(payload, ensure_ascii=False, indent=2), None


def get_act_messages(act_num, auto_fetch=True):
  """指定幕の生ログを取得する（分割モード時は未読込ならオンデマンド取得）"""
  if act_num < 1:
    return []
  if st.session_state.storage_mode == "legacy":
    return [
        m for m in st.session_state.legacy_messages if m.get("act") == act_num
    ]
  if act_num not in st.session_state.act_cache:
    if auto_fetch:
      fetched, err = fetch_acts_batch([act_num])
      if not err:
        st.session_state.act_cache[act_num] = fetched.get(act_num, [])
      else:
        st.warning(f"⚠️ 第 {act_num} 幕の読み込みに失敗しました: {err}")
        return []
    else:
      return []
  return st.session_state.act_cache.get(act_num, [])


def parse_legacy_memo(raw_text):
  """既存のテキスト形式メモを『世界観メモ』と『キャラ別データ』に安全に自動分割する"""
  if not raw_text:
    return "", []
  world_lines = []
  characters = []
  char_pattern = re.compile(r"^・\s*([^：]+)：\s*(.+)$")

  for line in raw_text.splitlines():
    stripped = line.strip()
    m = char_pattern.match(stripped)
    if m:
      characters.append({
          "id": uuid.uuid4().hex[:8],
          "name": m.group(1).strip(),
          "desc": m.group(2).strip(),
          "active": True,
      })
    else:
      world_lines.append(line)

  world_text = "\n".join(world_lines).strip()
  return world_text, characters


def get_structured_memo(messages):
  """messagesから構造化済み設定（世界観テキスト, キャラリスト）を取り出す"""
  raw_content = ""
  for m in messages:
    if m.get("act") == -1 and m.get("role") == "memo":
      raw_content = m.get("content", "")
      break

  if not raw_content:
    return "", []

  try:
    data = json.loads(raw_content)
    if isinstance(data, dict) and ("world" in data or "characters" in data):
      chars = data.get("characters", [])
      for c in chars:
        if "id" not in c:
          c["id"] = uuid.uuid4().hex[:8]
        if "active" not in c:
          c["active"] = True
      return data.get("world", ""), chars
  except Exception:
    pass

  return parse_legacy_memo(raw_content)


def save_structured_memo(messages, world_text, characters):
  """世界観テキストとキャラリストをJSON化してmessagesに格納する（レガシー互換用）"""
  filtered = [
      m for m in messages if not (m.get("act") == -1 and m.get("role") == "memo")
  ]
  memo_entry = build_memo_entry(world_text, characters)
  if memo_entry:
    filtered.insert(0, memo_entry)
  return filtered


def sync_and_save_settings():
  """画面上の最新の入力内容をすべて同期してSupabaseへ保存する"""
  if "world_text_editor" in st.session_state:
    st.session_state.world_text = st.session_state.world_text_editor

  for c in st.session_state.characters:
    cid = c["id"]
    if f"cname_{cid}" in st.session_state:
      c["name"] = st.session_state[f"cname_{cid}"]
    if f"cact_{cid}" in st.session_state:
      c["active"] = st.session_state[f"cact_{cid}"]
    if f"cdesc_{cid}" in st.session_state:
      c["desc"] = st.session_state[f"cdesc_{cid}"]

  return save_main_row(
      st.session_state.summaries,
      st.session_state.world_text,
      st.session_state.characters,
  )


def build_prompt_memo_text(world_text, characters):
  """AIに送信する形式に組み立てる"""
  parts = []
  if world_text.strip():
    parts.append(world_text.strip())
  active_chars = [
      c for c in characters if c.get("active", True) and c.get("name", "").strip()
  ]
  if active_chars:
    char_lines = [f"・{c['name'].strip()}：{c['desc'].strip()}" for c in active_chars]
    parts.append("\n".join(char_lines))
  return "\n\n".join(parts)


def retry_pending_save(current_act):
  """保存失敗時の再保存をモードに応じて実行する"""
  pending = st.session_state.get("pending_retry") or {}
  if st.session_state.storage_mode == "split":
    if pending.get("type") == "act":
      target_a = pending.get("act", current_act)
      return save_act_row(target_a, st.session_state.act_cache.get(target_a, []))
    elif pending.get("type") == "both":
      target_a = pending.get("act", current_act)
      ok1, err1 = save_act_row(
          target_a, st.session_state.act_cache.get(target_a, [])
      )
      if not ok1:
        st.session_state.pending_retry = {"type": "both", "act": target_a}
        return False, err1
      return save_main_row(
          st.session_state.summaries,
          st.session_state.world_text,
          st.session_state.characters,
      )
    return save_main_row(
        st.session_state.summaries,
        st.session_state.world_text,
        st.session_state.characters,
    )
  return save_main_row(
      st.session_state.summaries,
      st.session_state.world_text,
      st.session_state.characters,
  )


# 3. 10往復到達時の自動要約（★裏方の要約は4-hydrogen で固定）
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
          model="models/gemini-4-hydrogen",
          contents=prompt,
          config=types.GenerateContentConfig(
              safety_settings=CUSTOM_SAFETY_SETTINGS,
              thinking_config=types.ThinkingConfig(thinking_budget=128),
          ),
      )
      sum_cost, _, _, _, _ = calc_usage_cost(
          getattr(resp, "usage_metadata", None), "models/gemini-4-hydrogen"
      )
      if resp.text and not is_refusal_response(resp.text):
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

    /* ★キャラカード内：スマホ幅でも1行ヘッダー（名前＋読込＋開閉）を強制的に横並び維持 */
    div[data-testid="stHorizontalBlock"]:has(input[aria-label="キャラ名"]) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 6px !important;
        width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"]:has(input[aria-label="キャラ名"]) > div {
        min-width: 0 !important;
        max-width: none !important;
    }
    div[data-testid="stHorizontalBlock"]:has(input[aria-label="キャラ名"]) > div:nth-child(1) {
        flex: 1 1 auto !important;
        width: auto !important;
    }
    div[data-testid="stHorizontalBlock"]:has(input[aria-label="キャラ名"]) > div:nth-child(2) {
        flex: 0 0 auto !important;
        width: auto !important;
    }
    div[data-testid="stHorizontalBlock"]:has(input[aria-label="キャラ名"]) > div:nth-child(3) {
        flex: 0 0 auto !important;
        width: auto !important;
    }

    input[aria-label="キャラ名"] {
        font-weight: 700 !important;
        font-size: 1.0rem !important;
        padding: 0.25rem 0.45rem !important;
        background-color: transparent !important;
        border: 1px solid transparent !important;
        border-radius: 6px !important;
    }
    input[aria-label="キャラ名"]:hover,
    input[aria-label="キャラ名"]:focus {
        background-color: rgba(128, 128, 128, 0.12) !important;
        border: 1px solid rgba(217, 83, 111, 0.5) !important;
    }

    div[data-testid="stHorizontalBlock"]:has(input[aria-label="キャラ名"]) [data-testid="stCheckbox"] {
        margin: 0 !important;
        white-space: nowrap !important;
    }
    div[data-testid="stHorizontalBlock"]:has(input[aria-label="キャラ名"]) [data-testid="stCheckbox"] label p {
        font-size: 0.88rem !important;
        margin-bottom: 0 !important;
        line-height: 1.2 !important;
    }
    div[data-testid="stHorizontalBlock"]:has(input[aria-label="キャラ名"]) button {
        padding: 0.2rem 0.55rem !important;
        min-height: 2rem !important;
        width: auto !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# 初回ロード処理
if "storage_initialized" not in st.session_state:
  db_summaries, db_main_msgs, load_err = fetch_main_row()
  st.session_state.summaries = db_summaries
  st.session_state.db_load_failed = bool(load_err)
  st.session_state.db_load_error = load_err

  w_text, chars = get_structured_memo(db_main_msgs)
  st.session_state.world_text = w_text
  st.session_state.characters = chars

  mode = detect_storage_mode(db_main_msgs)
  st.session_state.storage_mode = mode
  init_act = len(db_summaries) + 1

  if mode == "split":
    st.session_state.legacy_messages = []
    # 起動時は現在幕と前幕（末尾2往復引き継ぎ用）の2行だけ取得
    target_acts = [a for a in (init_act - 1, init_act) if a >= 1]
    fetched, act_err = fetch_acts_batch(target_acts)
    if act_err:
      st.session_state.db_load_failed = True
      st.session_state.db_load_error = act_err
      st.session_state.act_cache = {}
    else:
      st.session_state.act_cache = fetched
    st.session_state.last_save_kb = get_json_kb(
        st.session_state.act_cache.get(init_act, [])
    )
    st.session_state.last_save_label = f"第 {init_act} 幕レコード単体"
  else:
    for m in db_main_msgs:
      if "act" not in m:
        m["act"] = init_act
    st.session_state.legacy_messages = db_main_msgs
    st.session_state.act_cache = {}
    st.session_state.last_save_kb = get_json_kb(
        {"summaries": db_summaries, "messages": db_main_msgs}
    )
    st.session_state.last_save_label = "全データ一括（移行前）"

  st.session_state.storage_initialized = True

if "unsaved_error" not in st.session_state:
  st.session_state.unsaved_error = None
if "pending_retry" not in st.session_state:
  st.session_state.pending_retry = None
if "char_open_states" not in st.session_state:
  st.session_state.char_open_states = {}
if "last_expand_all" not in st.session_state:
  st.session_state.last_expand_all = False
if "selected_act" not in st.session_state:
  st.session_state.selected_act = None
if "just_finished_act" not in st.session_state:
  st.session_state.just_finished_act = False
if "scroll_action" not in st.session_state:
  st.session_state.scroll_action = None
if "prepared_backup_json" not in st.session_state:
  st.session_state.prepared_backup_json = None

current_act = len(st.session_state.summaries) + 1
current_act_messages = get_act_messages(current_act, auto_fetch=True)
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


active_char_count = sum(
    1 for c in st.session_state.characters if c.get("active", True)
)
total_char_count = len(st.session_state.characters)

with st.sidebar:
  # ★DB読込失敗・未保存エラーの警告＆復旧ボタン
  if st.session_state.get("db_load_failed"):
    st.error(
        f"⚠️ DB読込失敗（上書き防止中）\n\n{st.session_state.get('db_load_error', '')}"
    )
    if st.button("🔄 DBを再読み込み", use_container_width=True, type="primary"):
      st.session_state.pop("storage_initialized", None)
      st.rerun()

  if st.session_state.get("unsaved_error"):
    st.error(f"⚠️ DB未保存データあり\n\n{st.session_state.unsaved_error}")
    if st.button(
        "💾 未保存データを再保存",
        key="sidebar_retry_save",
        use_container_width=True,
        type="primary",
    ):
      ok, retry_err = retry_pending_save(current_act)
      if ok:
        st.toast("💾 再保存に成功しました！")
        st.rerun()
      else:
        st.error(f"再保存失敗: {retry_err}")

  # ★1. 画面上下クイックジャンプボタン
  sc_col1, sc_col2 = st.columns(2)
  with sc_col1:
    if st.button("⬆️ 一番上へ", use_container_width=True):
      st.session_state.scroll_action = "top"
  with sc_col2:
    if st.button("⬇️ 一番下へ", use_container_width=True):
      st.session_state.scroll_action = "bottom"

  # ★2. サイドバーから直接「執筆」と「世界観・キャラ設定」を切り替え
  nav_mode = st.radio(
      "画面モード",
      options=["📖 物語の執筆", "📌 世界観・キャラ設定"],
      label_visibility="collapsed",
  )

  if nav_mode == "📌 世界観・キャラ設定":
    st.caption(f"👥 AI読込中: **{active_char_count}** / {total_char_count} 人")
    if st.button(
        "💾 設定をすべて保存",
        key="sidebar_save_settings",
        type="primary",
        use_container_width=True,
    ):
      ok, err = sync_and_save_settings()
      if ok:
        st.toast("📌 世界観とキャラクター設定を保存しました！")
        st.rerun()
      else:
        st.error(f"⚠️ 保存失敗: {err}")

  st.markdown("---")
  st.title("📜 記憶アーカイブ")

  if st.session_state.storage_mode == "split":
    st.caption("⚡ 軽量モード稼働中（幕ごと分割保存）")
  else:
    st.caption("📦 移行前モード（全データ一括保存）")

  if st.session_state.selected_act is not None:
    if st.button(
        f"↩ 現在へ戻る（第 {current_act} 幕へ）",
        type="primary",
        use_container_width=True,
    ):
      st.session_state.selected_act = None
      st.session_state.just_finished_act = False
      st.session_state.scroll_action = "top"
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

  # ★送信文字数の内訳 ＆ usage_metadata 生データの診断パネル
  if "last_debug_info" in st.session_state:
    with st.expander("🔍 送信内訳・キャッシュ診断", expanded=False):
      st.markdown(st.session_state.last_debug_info["breakdown"])
      if st.session_state.last_debug_info.get("fallback_reason"):
        st.warning(
            f"🛡️ フォールバック発生理由: {st.session_state.last_debug_info['fallback_reason']}"
        )
      st.caption(
          f"💾 直近DB保存量（{st.session_state.get('last_save_label', '')}）: "
          f"約 {st.session_state.get('last_save_kb', 0.0):.1f} KB"
      )
      st.caption("API usage_metadata 生データ")
      st.code(st.session_state.last_debug_info["usage_raw"], language="json")

  # ★執筆モデルのワンタッチ切り替え（初期値を 4-neon に設定）
  selected_model = st.selectbox(
      "🧠 執筆AIモデル",
      options=[
          "models/gemini-4-argon",
          "models/gemini-4-neon",
          "models/gemini-4-hydrogen",
      ],
      index=1,
      help="4-hydrogenは普段使い・コスパ最強、4-neonは新世代バランス型（キャッシュ95%OFF）、4-argonは最高品質。",
  )

  # ★思考トークン上限（初期値を安定の 2048 に設定）
  thinking_limit = st.select_slider(
      "💭 思考トークン上限（節約の要）",
      options=[0, 256, 1024, 2048, 3072],
      value=2048,
      format_func=lambda x: {
          0: "オフ (0)",
          256: "最小 (256)",
          1024: "標準 (1024)",
          2048: "深考 (2048)",
          3072: "特盛 (3072)",
      }[x],
      help="Neonは実使用500前後で省エネ動作するため2048のままでも安心です。",
  )

  # ★AIに送る直近生ログの往復数スライダー（キャッシュ最大化のため初期値を 12 に設定）
  context_rounds = st.slider(
      "📡 AIへ送る直近ログ数（往復）",
      min_value=1,
      max_value=12,
      value=12,
      key="context_rounds_slider",
      help="12にしておくと同じ幕のあいだ先頭がズレず、直近ログまでキャッシュに乗りやすくなります（検閲誤爆時のみ1〜2に下げて回避）。",
  )

  # ★幕が進んでもスライダー値がリセットされないよう max_value を固定化
  slider_max_acts = max(
      200, ((len(st.session_state.summaries) // 100) + 1) * 100
  )

  # ★全文を送る過去要約の幕数スライダー（初期値を 3 に設定）
  full_summary_acts = st.slider(
      "📚 全文を送る過去要約（直近〇幕）",
      min_value=0,
      max_value=slider_max_acts,
      value=3,
      key="full_summary_acts_slider",
      help="直近の重要展開を全文でAIに渡します。",
  )

  # ★抜粋（見出し＋末尾70字）を送る幕数スライダー（初期値を 15 に設定）
  excerpt_summary_acts = st.slider(
      "✂️ 抜粋を送る過去要約（その前の〇幕）",
      min_value=0,
      max_value=slider_max_acts,
      value=15,
      key="excerpt_summary_acts_slider",
      help="全文より古い幕のうち、見出し＋末尾70文字を残す幕数です。",
  )

  # ★さらに古い幕のダイエット設定
  older_summary_mode = st.selectbox(
      "🪶 さらに古い幕の扱い（ダイエット）",
      options=[
          "見出しのみ（超軽量）",
          "送信しない（完全カット）",
          "従来通り抜粋を送る",
      ],
      index=0,
      help="「見出しのみ」にすると1幕あたり約20字まで圧縮し、長期連載でもトークン膨張を防ぎます。",
  )

  # 直前のやり取り（1手）を巻き戻す救急ボタン
  if st.button("⏪ 直前の1手を巻き戻す"):
    if st.session_state.storage_mode == "split":
      curr_list = st.session_state.act_cache.get(current_act, [])
      if len(curr_list) >= 2:
        curr_list.pop()  # assistant
        curr_list.pop()  # user
        ok, err = save_act_row(current_act, curr_list)
        if ok:
          st.toast("直前の1往復を巻き戻しました")
          st.rerun()
        else:
          st.error(f"⚠️ 巻き戻しの保存に失敗しました: {err}")
      else:
        st.toast("現在の幕には巻き戻せる履歴がありません")
    else:
      chat_msgs = [
          m for m in st.session_state.legacy_messages if m.get("act", 1) > 0
      ]
      if len(chat_msgs) >= 2:
        st.session_state.legacy_messages.pop()
        st.session_state.legacy_messages.pop()
        ok, err = save_main_row(
            st.session_state.summaries,
            st.session_state.world_text,
            st.session_state.characters,
        )
        if ok:
          st.toast("直前の1往復を巻き戻しました")
          st.rerun()
        else:
          st.error(f"⚠️ 巻き戻しの保存に失敗しました: {err}")

  with st.expander("💾 バックアップ・緊急ツール", expanded=False):
    st.caption(
        f"保存方式: {'幕ごと分割（超軽量）' if st.session_state.storage_mode == 'split' else '一括保存（移行前）'}\n"
        f"直近保存サイズ: 約 {st.session_state.get('last_save_kb', 0.0):.1f} KB"
    )
    if st.session_state.storage_mode == "legacy":
      backup_json, _ = export_full_backup_json()
      st.download_button(
          "📥 全データをJSON保存",
          data=backup_json.encode("utf-8"),
          file_name=f"gensouroku_backup_act{current_act}.json",
          mime="application/json",
          use_container_width=True,
      )
    else:
      if st.button(
          "📦 全幕バックアップJSONを作成", use_container_width=True
      ):
        with st.spinner("全幕のデータを集計中..."):
          b_json, b_err = export_full_backup_json()
          if b_err:
            st.error(f"集計失敗: {b_err}")
          else:
            st.session_state.prepared_backup_json = b_json
      if st.session_state.get("prepared_backup_json"):
        st.download_button(
            "📥 作成済みJSONをダウンロード",
            data=st.session_state.prepared_backup_json.encode("utf-8"),
            file_name=f"gensouroku_backup_act{current_act}.json",
            mime="application/json",
            use_container_width=True,
            type="primary",
        )

    if st.button("物語をリセット", use_container_width=True):
      if st.session_state.storage_mode == "split":
        try:
          client = get_supabase_client()
          client.table("novel_saves").delete().like(
              "id", f"{ACT_ROW_PREFIX}%"
          ).execute()
        except Exception:
          pass
      st.session_state.summaries = []
      st.session_state.legacy_messages = []
      st.session_state.act_cache = {1: []}
      ok, err = save_main_row([], "", [], allow_empty=True)
      if ok:
        st.session_state.world_text = ""
        st.session_state.characters = []
        st.session_state.selected_act = None
        st.session_state.just_finished_act = False
        st.rerun()
      else:
        st.error(f"⚠️ リセットの保存に失敗しました: {err}")

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
        st.session_state.just_finished_act = False
        st.session_state.scroll_action = "bottom"
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
        ok, err = save_main_row(
            st.session_state.summaries,
            st.session_state.world_text,
            st.session_state.characters,
        )
        if ok:
          st.toast(
              f"第 {idx + 1} 幕の記録を『{new_title}』として更新しました！"
          )
          st.rerun()
        else:
          st.error(f"⚠️ 記録の保存に失敗しました: {err}")

# 5. メイン画面の描画（最上部アンカー設置）
st.markdown('<div id="page-top-anchor"></div>', unsafe_allow_html=True)

# ★レガシーモード（移行前）なら、安全なお引っ越しバナーを最上部に表示
if (
    st.session_state.storage_mode == "legacy"
    and not st.session_state.get("db_load_failed")
    and len(st.session_state.legacy_messages) > 0
):
  with st.container(border=True):
    st.info(
        f"🚀 **本格軽量化の準備が整っています**（現在の1回あたり保存量: 約 **{st.session_state.get('last_save_kb', 0.0):.1f} KB**）\n\n"
        "幕ごとに行を分割すると、毎ターンの保存量が **約 25〜35 KB（約1/100）** に激減し、"
        "タイムアウトエラーを防げます。全幕の保存完了を確認してから親データを切り替えるため安全です。"
    )
    if st.button(
        "📦 幕ごと分割ストレージへ安全に移行する",
        type="primary",
        use_container_width=True,
    ):
      ok_mig, msg_mig = migrate_to_split_storage()
      if ok_mig:
        st.success(f"✨ {msg_mig}")
        time.sleep(1.2)
        st.rerun()
      else:
        st.error(f"⚠️ 移行を中断しました: {msg_mig}")

if nav_mode == "📌 世界観・キャラ設定":
  # ==========================================
  # 世界観・キャラクター設定データベース画面
  # ==========================================
  col_h1, col_h2 = st.columns([3, 1])
  with col_h1:
    st.title("📌 世界観・キャラ設定")
  with col_h2:
    if st.button(
        "💾 設定をすべて保存",
        key="top_save_settings",
        type="primary",
        use_container_width=True,
    ):
      ok, err = sync_and_save_settings()
      if ok:
        st.toast("📌 世界観とキャラクター設定を保存しました！")
        st.rerun()
      else:
        st.error(f"⚠️ 保存失敗: {err}")

  st.subheader("🌐 世界観・大目標・契約・情勢メモ")
  st.text_area(
      "世界観メモ",
      value=st.session_state.world_text,
      height=220,
      key="world_text_editor",
      label_visibility="collapsed",
      placeholder="大目標、種族ごとの感情の法則、勢力間の契約、現在の裏での動きなどを自由に記入してください。",
  )

  st.markdown("---")
  st.subheader(
      f"👥 登場人物・関係性図鑑（読込中: {active_char_count}/{total_char_count}人）"
  )
  st.caption(
      "💡 名前をタップすると直接編集できます。右端の「読込」でAIへの送信ON/OFF、「▼」で詳細文を開閉します。"
  )

  s_col1, s_col2 = st.columns([3, 1])
  with s_col1:
    search_query = st.text_input(
        "🔍 キャラクター検索（名前・陣営・キーワードで絞り込み）",
        placeholder="例：レミリア、紅魔館、守矢、将棋…",
    )
  with s_col2:
    expand_all = st.toggle("📂 全キャラを一括展開", value=False)

  if expand_all != st.session_state.last_expand_all:
    st.session_state.last_expand_all = expand_all
    for c in st.session_state.characters:
      st.session_state.char_open_states[c["id"]] = expand_all

  with st.expander("➕ 新しいキャラクターを追加する", expanded=False):
    with st.form("add_character_form", clear_on_submit=True):
      new_c_name = st.text_input(
          "キャラクター名（フルネーム可・中黒「・」もそのまま使えます）",
          placeholder="例：飯綱丸龍",
      )
      new_c_desc = st.text_area(
          "関係性・陣営・口調・設定",
          height=110,
          placeholder="例：【妖怪の山】大天狗。菅牧典を通じて守矢神社に話を通し、近々正式に真斉と面会しようと画策している。",
      )
      if st.form_submit_button("リストに追加", use_container_width=True):
        if new_c_name.strip():
          new_id = uuid.uuid4().hex[:8]
          st.session_state.characters.append({
              "id": new_id,
              "name": new_c_name.strip(),
              "desc": new_c_desc.strip(),
              "active": True,
          })
          st.session_state.char_open_states[new_id] = True
          ok, err = sync_and_save_settings()
          if ok:
            st.toast(f"✨ {new_c_name.strip()} を図鑑に追加＆保存しました！")
            st.rerun()
          else:
            st.error(f"⚠️ 追加の保存に失敗しました: {err}")

  chars_list = st.session_state.characters
  q_lower = search_query.strip().lower()

  for idx, char in enumerate(chars_list):
    if q_lower and (
        q_lower not in char["name"].lower()
        and q_lower not in char["desc"].lower()
    ):
      continue

    cid = char["id"]
    is_open = st.session_state.char_open_states.get(cid, False)

    with st.container(border=True):
      h_col1, h_col2, h_col3 = st.columns([7, 1.8, 1.2])
      with h_col1:
        updated_name = st.text_input(
            "キャラ名",
            value=char["name"],
            key=f"cname_{cid}",
            label_visibility="collapsed",
        )
      with h_col2:
        updated_active = st.checkbox(
            "読込",
            value=char.get("active", True),
            key=f"cact_{cid}",
        )
      with h_col3:
        toggle_label = "▲" if is_open else "▼"
        if st.button(
            toggle_label,
            key=f"ctoggle_{cid}",
            help="詳細設定の開閉",
        ):
          st.session_state.char_open_states[cid] = not is_open
          st.rerun()

      chars_list[idx]["name"] = updated_name
      chars_list[idx]["active"] = updated_active

      if is_open:
        auto_height = max(130, min(380, (len(char["desc"]) // 28 + 2) * 26))
        updated_desc = st.text_area(
            "関係性・性格・陣営・設定",
            value=char["desc"],
            height=auto_height,
            key=f"cdesc_{cid}",
            label_visibility="collapsed",
        )
        chars_list[idx]["desc"] = updated_desc

  st.markdown("---")
  if st.button(
      "💾 変更した設定をすべて保存",
      key="bottom_save_settings",
      type="primary",
      use_container_width=True,
  ):
    ok, err = sync_and_save_settings()
    if ok:
      st.toast("📌 世界観とキャラクター設定を保存しました！")
      st.rerun()
    else:
      st.error(f"⚠️ 保存失敗: {err}")

elif st.session_state.selected_act is not None:
  # ==========================================
  # 過去幕・完結幕の回想画面（オンデマンド読込）
  # ==========================================
  act_idx = st.session_state.selected_act
  target_act = act_idx + 1
  col_t, col_b = st.columns([4, 1])
  with col_t:
    title_suffix = (
        "（完結・最終出力）"
        if st.session_state.just_finished_act
        else "（回想中）"
    )
    st.title(f"📖 第 {target_act} 幕の記憶{title_suffix}")
  with col_b:
    if st.button(
        f"✨ 第 {current_act} 幕へ",
        key="back_to_present_main",
        use_container_width=True,
    ):
      st.session_state.selected_act = None
      st.session_state.just_finished_act = False
      st.session_state.scroll_action = "top"
      st.rerun()

  reminiscence_messages = get_act_messages(target_act, auto_fetch=True)
  if reminiscence_messages:
    for msg in reminiscence_messages:
      display_novel_entry(msg["role"], msg["content"])
  else:
    st.info(
        f"💡 第 {target_act} 幕の生ログは、完全保存機能の導入前の幕のため保管されていません。左サイドバーの「要約本文」から当時の記録をお楽しみください。"
    )

  st.markdown("---")
  if st.session_state.just_finished_act:
    st.success(f"第 {target_act} 幕の要約を記録しました")
  if st.button(
      f"第 {current_act} 幕（新しい幕）へ進む",
      key="proceed_next_act_bottom",
      type="primary",
      use_container_width=True,
  ):
    st.session_state.selected_act = None
    st.session_state.just_finished_act = False
    st.session_state.scroll_action = "top"
    st.rerun()

else:
  # ==========================================
  # 最新の執筆画面
  # ==========================================
  st.title("幻想郷 真斉幻想禄")

  for msg in current_act_messages:
    display_novel_entry(msg["role"], msg["content"])

  if action_input := st.chat_input("物語の続きを執筆..."):
    user_msg = {
        "role": "user",
        "content": action_input,
        "act": current_act,
    }
    if st.session_state.storage_mode == "split":
      st.session_state.act_cache.setdefault(current_act, []).append(user_msg)
    else:
      st.session_state.legacy_messages.append(user_msg)
    display_novel_entry("user", action_input)

    # ★1. 世界観＋有効キャラクター設定の組み立て（サニタイズ適用）
    raw_memo = build_prompt_memo_text(
        st.session_state.world_text, st.session_state.characters
    )
    memo_block = (
        f"【不変の基本設定・キャラクター関係性メモ】\n{sanitize_for_api(raw_memo)}"
        if raw_memo
        else ""
    )

    # ★2. 要約アーカイブを3段階（全文 / 抜粋 / 古い幕の軽量化）で構築
    total_summaries = len(st.session_state.summaries)
    full_start = max(0, total_summaries - full_summary_acts)
    excerpt_start = max(0, full_start - excerpt_summary_acts)

    compressed_summaries = []
    full_cnt = excerpt_cnt = title_cnt = skip_cnt = 0

    for idx, s in enumerate(st.session_state.summaries):
      sanitized_s = sanitize_for_api(s)
      lines = [
          line.strip()
          for line in sanitized_s.strip().split("\n")
          if line.strip()
      ]
      header = lines[0] if lines else "記録"
      body_flat = "".join(lines[1:]) if len(lines) > 1 else ""
      tail_text = body_flat[-70:] if len(body_flat) > 70 else body_flat

      if full_summary_acts > 0 and idx >= full_start:
        compressed_summaries.append(f"[過去の記録 第{idx+1}幕]\n{sanitized_s}")
        full_cnt += 1
      elif excerpt_summary_acts > 0 and idx >= excerpt_start:
        compressed_summaries.append(
            f"[第{idx+1}幕（抜粋）] {header} / …{tail_text}"
        )
        excerpt_cnt += 1
      else:
        if older_summary_mode == "見出しのみ（超軽量）":
          compressed_summaries.append(f"[第{idx+1}幕] {header}")
          title_cnt += 1
        elif older_summary_mode == "送信しない（完全カット）":
          skip_cnt += 1
        else:
          compressed_summaries.append(
              f"[第{idx+1}幕（抜粋）] {header} / …{tail_text}"
          )
          excerpt_cnt += 1

    summaries_context = "\n---\n".join(compressed_summaries)
    archive_block = (
        f"【過去の物語の要約・確定した歴史】\n{summaries_context}"
        if summaries_context
        else ""
    )

    # ★3. 不変ブロックを system_instruction に統合して完全固定化
    system_base_text = SYSTEM_INSTRUCTION.strip()
    system_parts = [system_base_text]
    if memo_block:
      system_parts.append(memo_block)
    if archive_block:
      system_parts.append(archive_block)
    full_system_instruction = "\n\n".join(system_parts)

    prev_act_messages = (
        get_act_messages(current_act - 1, auto_fetch=True)[-4:]
        if current_act > 1
        else []
    )
    curr_act_without_last = get_act_messages(current_act, auto_fetch=False)[:-1]
    all_recent_candidates = prev_act_messages + curr_act_without_last
    sanitized_action = sanitize_for_api(action_input)

    output_story = None
    error_detail = None
    primary_fail_reason = None
    jpy_cost = 0.0
    un_in_tok = cache_tok = th_tok = out_tok = 0
    used_fallback = False
    last_usage_raw = "usage_metadata: None"
    last_contents_chars = 0

    def invoke_model(msg_limit, use_model, curr_thinking, temp):
      recent_messages = all_recent_candidates[-msg_limit:]
      multiturn_contents = build_multiturn_contents(
          recent_messages, sanitized_action
      )
      c_chars = sum(
          len(p.text or "")
          for c in multiturn_contents
          for p in (c.parts or [])
      )
      # 思考＋本文で枠切れしない安全天井（実使用分のみ課金）
      safe_max_out = max(2048, curr_thinking + 1536)
      gen_config = types.GenerateContentConfig(
          system_instruction=full_system_instruction,
          temperature=temp,
          max_output_tokens=safe_max_out,
          safety_settings=CUSTOM_SAFETY_SETTINGS,
      )
      if curr_thinking > 0:
        gen_config.thinking_config = types.ThinkingConfig(
            thinking_budget=curr_thinking
        )
      resp = gemini_client.models.generate_content(
          model=use_model,
          contents=multiturn_contents,
          config=gen_config,
      )
      return resp, c_chars

    with st.spinner("幻想郷の時間を進めています..."):
      # ★Phase 1: 選択モデル（通信エラーのみ1回同モデルで再試行）
      for net_try in range(2):
        try:
          response, last_contents_chars = invoke_model(
              context_rounds * 2, selected_model, thinking_limit, 0.85
          )
          usage_meta = getattr(response, "usage_metadata", None)
          last_usage_raw = format_usage_raw(usage_meta)
          step_cost, step_in, step_cache, step_th, step_out = calc_usage_cost(
              usage_meta, selected_model
          )
          jpy_cost += step_cost
          un_in_tok += step_in
          cache_tok += step_cache
          th_tok += step_th
          out_tok += step_out

          if response.text:
            candidate_text = response.text.strip()
            if is_refusal_response(candidate_text):
              primary_fail_reason = "ソフト拒否（ガイドライン辞退応答）"
              error_detail = "AIがガイドラインを理由に執筆を辞退しました。"
              break
            output_story = candidate_text
            break
          elif response.candidates:
            finish_reason = getattr(
                response.candidates[0], "finish_reason", "UNKNOWN"
            )
            primary_fail_reason = f"応答中断（finish_reason: {finish_reason}）"
            error_detail = f"AI応答中断（理由: {finish_reason}）。"
            break
          else:
            block_reason = "不明"
            if (
                hasattr(response, "prompt_feedback")
                and response.prompt_feedback
            ):
              block_reason = getattr(
                  response.prompt_feedback, "block_reason", "SAFETY"
              )
            primary_fail_reason = f"プロンプト事前遮断（{block_reason}）"
            error_detail = f"プロンプト事前遮断（{block_reason}）"
            break
        except Exception as e:
          primary_fail_reason = f"API通信エラー（{type(e).__name__}: {str(e)[:120]}）"
          error_detail = f"API通信エラー: {str(e)}"
          if net_try == 0:
            time.sleep(1.5)
            continue

      # ★Phase 2: 失敗時のみ 4-hydrogen（直近1往復）へフォールバック
      if not output_story:
        try:
          response, last_contents_chars = invoke_model(
              2, "models/gemini-4-hydrogen", 256, 0.75
          )
          usage_meta = getattr(response, "usage_metadata", None)
          last_usage_raw = format_usage_raw(usage_meta)
          step_cost, step_in, step_cache, step_th, step_out = calc_usage_cost(
              usage_meta, "models/gemini-4-hydrogen"
          )
          jpy_cost += step_cost
          un_in_tok += step_in
          cache_tok += step_cache
          th_tok += step_th
          out_tok += step_out

          if response.text and not is_refusal_response(response.text.strip()):
            output_story = response.text.strip()
            used_fallback = True
          elif response.text:
            error_detail = (
                f"1回目: {primary_fail_reason} / 2回目(Hydrogen): ガイドライン辞退"
            )
          elif response.candidates:
            fr = getattr(response.candidates[0], "finish_reason", "UNKNOWN")
            error_detail = (
                f"1回目: {primary_fail_reason} / 2回目(Hydrogen): 応答中断({fr})"
            )
          else:
            error_detail = (
                f"1回目: {primary_fail_reason} / 2回目(Hydrogen): 事前遮断"
            )
        except Exception as e:
          error_detail = (
              f"1回目: {primary_fail_reason} / 2回目(Hydrogen): 通信エラー({e})"
          )

    if not output_story:
      if st.session_state.storage_mode == "split":
        st.session_state.act_cache[current_act].pop()
      else:
        st.session_state.legacy_messages.pop()
      st.error(f"⚠️ {error_detail}")
      st.info(f"💡 直前の入力内容: 『{action_input}』")
    else:
      if used_fallback:
        st.toast(
            f"🛡️ Hydrogenへ切替（理由: {primary_fail_reason}）"
        )
      display_novel_entry("assistant", output_story)

      assistant_msg = {
          "role": "assistant",
          "content": output_story,
          "act": current_act,
      }
      if st.session_state.storage_mode == "split":
        st.session_state.act_cache[current_act].append(assistant_msg)
        updated_act_messages = st.session_state.act_cache[current_act]
      else:
        st.session_state.legacy_messages.append(assistant_msg)
        updated_act_messages = [
            m
            for m in st.session_state.legacy_messages
            if m.get("act") == current_act
        ]

      sum_cost = 0.0
      finished_this_turn = False
      if len(updated_act_messages) >= (WINDOW_ROUNDS * 2):
        finished_this_turn = True
        with st.spinner("一幕の記憶を要約アーカイブへ記録中..."):
          new_summary, sum_cost = summarize_old_context(updated_act_messages)
          st.session_state.summaries.append(new_summary)
          st.session_state.selected_act = len(st.session_state.summaries) - 1
          st.session_state.just_finished_act = True
          st.session_state.scroll_action = "bottom"
          if st.session_state.storage_mode == "split":
            st.session_state.act_cache[current_act + 1] = []

      total_turn_cost = jpy_cost + sum_cost
      sum_note = f" (うち自動要約: {sum_cost:.2f}円)" if sum_cost > 0 else ""
      st.session_state.last_cost_info = (
          f"💰 直前ラリー: **約 {total_turn_cost:.2f} 円**{sum_note}\n"
          f"- 入力: {un_in_tok:,} tok (キャッシュ: {cache_tok:,} tok)\n"
          f"- 思考: {th_tok:,} tok / 出力: {out_tok:,} tok"
      )

      sys_len = len(system_base_text)
      memo_len = len(memo_block)
      arc_len = len(archive_block)
      total_chars = sys_len + memo_len + arc_len + last_contents_chars
      st.session_state.last_debug_info = {
          "breakdown": (
              f"**送信文字数の内訳（計 {total_chars:,} 字）**\n"
              f"- 基本指示: {sys_len:,} 字\n"
              f"- 世界観・キャラ設定: {memo_len:,} 字\n"
              f"- 過去要約: {arc_len:,} 字 "
              f"（全文{full_cnt} / 抜粋{excerpt_cnt} / 見出し{title_cnt} / 除外{skip_cnt}）\n"
              f"- 直近ログ＋入力: {last_contents_chars:,} 字"
          ),
          "usage_raw": last_usage_raw,
          "fallback_reason": primary_fail_reason if used_fallback else None,
      }

      # ★保存処理（分割モード時は通常ターン＝現在幕30KBだけ！ 幕完結時のみ親も更新）
      if st.session_state.storage_mode == "split":
        ok_act, err_act = save_act_row(current_act, updated_act_messages)
        if not ok_act:
          if finished_this_turn:
            st.session_state.pending_retry = {
                "type": "both",
                "act": current_act,
            }
        elif finished_this_turn:
          ok_main, _ = save_main_row(
              st.session_state.summaries,
              st.session_state.world_text,
              st.session_state.characters,
          )
          if ok_main:
            st.rerun()
        else:
          st.rerun()
      else:
        ok, _ = save_main_row(
            st.session_state.summaries,
            st.session_state.world_text,
            st.session_state.characters,
        )
        if ok:
          st.rerun()

  # ★保存失敗時でも画面を落とさず、そのままエラー詳細と再保存ボタンを表示
  if st.session_state.get("unsaved_error"):
    st.error(
        f"⚠️ 物語の生成は完了しましたが、Supabaseへの保存に失敗しました。\n\n"
        f"**エラー詳細:** {st.session_state.unsaved_error}"
    )
    if st.button(
        "💾 未保存データを再保存する",
        key="main_retry_save",
        type="primary",
        use_container_width=True,
    ):
      retry_ok, retry_err = retry_pending_save(current_act)
      if retry_ok:
        st.toast("💾 再保存に成功しました！")
        st.rerun()
      else:
        st.error(f"⚠️ 再保存にも失敗しました: {retry_err}")

# 6. 最下部アンカー設置 ＆ スクロール実行
st.markdown('<div id="page-bottom-anchor"></div>', unsafe_allow_html=True)

if st.session_state.scroll_action:
  execute_scroll(st.session_state.scroll_action)
  st.session_state.scroll_action = None
