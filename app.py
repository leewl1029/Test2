"""AI 관상가 - 얼굴 사진을 OpenAI 이미지 분석 모델로 풀이하는 Streamlit 앱."""

import base64
import datetime
import hashlib
import os
import threading
import time
from io import BytesIO

import openai
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageOps

st.set_page_config(page_title="AI 관상가", page_icon="🔮", layout="centered")

load_dotenv()

DISCLAIMER = "본 결과는 재미를 위한 것이며 과학적 근거가 없습니다."
PRIVACY_NOTICE = "사진은 저장되지 않으며 분석을 위해 OpenAI로 전송됩니다."
# gpt-4o-mini는 얼굴 기반 관상 풀이를 거절하고 "얼굴을 찾기 어렵습니다"로 대신 답하는 경우가 많아 교체함
DEFAULT_MODEL = "gpt-5.4-mini"
MAX_FILE_BYTES = 10 * 1024 * 1024
# 파일 용량은 작아도 픽셀 수가 큰 이미지는 열 때 메모리를 크게 쓴다 (12000x12000 PNG 434KB → 약 1.2GB)
MAX_PIXELS = 25_000_000
MAX_SIDE = 1024
# 공개 배포 시 API 비용 남용 방지
SESSION_LIMIT = 10          # 브라우저 세션당 최대 분석 횟수
COOLDOWN_SECONDS = 10       # 분석 사이 최소 간격
DEFAULT_DAILY_LIMIT = 200   # 앱 전체 하루 최대 분석 횟수 (Secrets의 DAILY_LIMIT로 변경 가능)
NO_FACE_PREFIX = "얼굴을 찾기 어렵습니다"
REFUSAL_MESSAGE = "모델이 이 사진의 관상 풀이를 거절했습니다. 얼굴이 잘 보이는 다른 사진으로 다시 시도해 주세요."
# gpt-5 계열은 추론 토큰도 이 한도에 포함되므로 넉넉하게 잡는다
MAX_OUTPUT_TOKENS = 4000
ALLOWED_TYPES = ["jpg", "jpeg", "png", "webp"]

SYSTEM_PROMPT = """당신은 '도사'라는 이름의 유쾌한 한국 전통 관상가 캐릭터입니다.
이 앱은 사용자가 재미로 자기 사진을 올리고 전통 관상 풀이를 받아 보는 엔터테인먼트 서비스이며, 사용자는 결과가 과학적 근거가 없는 놀이라는 점을 알고 동의했습니다.

할 일:
사진에서 눈에 보이는 얼굴 특징(이마의 넓이, 눈썹 모양, 눈매, 코의 형태, 입술, 턱선과 얼굴형, 귀 등)을 관찰하고,
그 특징을 전통 관상학의 해석에 빗대어 따뜻하고 긍정적인 이야기로 풀어 주세요.
이것은 사람을 판단하거나 신원을 밝히는 일이 아니라, 전통 관상 놀이 형식의 덕담입니다.

출력 형식 (한국어, Markdown, 제목을 아래와 똑같이 쓰고 순서 지키기):
## 🌟 첫인상
한 줄 요약
## 🔍 부위별 풀이
### 🧠 이마
### 〰️ 눈썹
### 👁️ 눈
### 👃 코
### 👄 입
### 🌙 턱·얼굴형
### 👂 귀
(귀가 사진에서 보이지 않으면 이 소제목은 통째로 생략합니다. 괄호 안 안내문은 출력하지 않습니다.)
## 🍀 운세 풀이
- **💰 재물운**: 2~3문장
- **💕 애정운**: 2~3문장
- **💼 직업운**: 2~3문장
- **🌿 건강운**: 가볍게 2~3문장
## 📜 총평 및 조언
## 🐾 닮은 동물상
한 가지와 그 이유

규칙:
- 외모를 비하하거나 상처가 될 표현은 쓰지 않습니다.
- 사진 속 인물이 누구인지 밝히거나 추측하지 않습니다. 유명인처럼 보여도 이름을 말하지 않습니다.
- 인종, 민족, 종교, 성적 지향, 건강 상태는 추정하지 않습니다.
- 그림, 일러스트, 흐릿하거나 옆을 본 사진이어도 얼굴 특징이 조금이라도 보이면 보이는 부분만으로 풀이합니다.
- 사진에 사람의 얼굴이 전혀 없을 때(풍경, 사물, 단색 이미지 등)에만 다른 내용 없이 "얼굴을 찾기 어렵습니다. 얼굴이 잘 보이는 정면 사진을 올려 주세요."라고만 답합니다.
- 풀이를 한 경우에만 마지막 줄에 "재미로 보는 관상입니다 🔮"를 넣습니다."""

USER_PROMPT = "이 사진 속 인물의 관상을 정해진 형식대로 풀이해 주세요."


def get_secret(name, default=None):
    """st.secrets → 환경변수(.env) 순서로 설정값을 읽는다."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        # 로컬에서 secrets.toml이 없으면 예외가 발생하므로 무시
        pass
    return os.getenv(name, default)


@st.cache_resource
def get_client(api_key):
    """OpenAI 클라이언트를 한 번만 만들어 재사용한다."""
    return openai.OpenAI(api_key=api_key)


class ImageTooLargeError(Exception):
    """픽셀 수가 MAX_PIXELS를 넘는 이미지."""


@st.cache_resource
def get_daily_counter():
    """앱 전체(모든 사용자)가 공유하는 하루 분석 횟수 카운터."""
    return {"date": None, "count": 0, "lock": threading.Lock()}


def load_image(data):
    """이미지 바이트를 열어 EXIF 회전을 보정하고 RGB로 변환한다. 픽셀 수가 너무 크면 거부한다."""
    image = Image.open(BytesIO(data))  # 헤더만 읽고 아직 픽셀은 풀지 않는다
    width, height = image.size
    if width * height > MAX_PIXELS:
        raise ImageTooLargeError
    # JPEG는 디코딩 단계에서 미리 줄여 메모리를 아낀다
    image.draft("RGB", (MAX_SIDE * 2, MAX_SIDE * 2))
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        # 투명 배경은 흰색으로 채운다
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        image = background
    return image


def resize_image(image, max_side=MAX_SIDE):
    """긴 변이 max_side 이하가 되도록 비율을 유지하며 줄인다. (전달된 이미지를 직접 줄인다)"""
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return image


@st.cache_data(max_entries=20, show_spinner=False)
def prepare_image(data):
    """업로드 바이트 → 회전 보정·RGB·축소 후 JPEG 바이트. 같은 사진은 다시 처리하지 않는다."""
    image = resize_image(load_image(data))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def encode_image(jpeg_bytes):
    """JPEG 바이트를 base64 data URL로 인코딩한다."""
    encoded = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def analyze_face(client, model, image_data_url):
    """OpenAI 이미지 분석 모델로 관상 풀이를 요청하고 Markdown 텍스트를 돌려준다."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url, "detail": "auto"},
                    },
                ],
            },
        ],
        max_completion_tokens=MAX_OUTPUT_TOKENS,
    )
    message = response.choices[0].message
    if getattr(message, "refusal", None):
        return REFUSAL_MESSAGE
    return (message.content or "").strip()


# ---------------------------------------------------------------- UI

def inject_css():
    """커스텀 글꼴과 스타일을 한곳에서 적용한다. (data-testid / st-key-* 선택자만 사용)"""
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@700;800&family=Noto+Sans+KR:wght@400;500;700&display=swap');

:root {
  --gold: #C9A227;
  --gold-soft: #E6C766;
  --ink: #0F1626;
  --hanji: #F7F1E3;
  --hanji-line: #E2D5B5;
  --hanji-text: #2B2418;
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"],
button, input, label {
  font-family: 'Noto Sans KR', sans-serif;
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(ellipse at top, rgba(201,162,39,0.14), transparent 60%),
    var(--ink);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { padding-top: 2.5rem; padding-bottom: 3rem; }

/* 헤더 */
.gs-header { text-align: center; margin-bottom: 1.5rem; }
.gs-header .gs-icon { font-size: 3rem; line-height: 1; }
.gs-header h1 {
  font-family: 'Nanum Myeongjo', serif;
  font-weight: 800;
  font-size: 2.6rem;
  color: var(--gold-soft);
  letter-spacing: 0.08em;
  margin: 0.4rem 0 0.3rem;
  padding: 0;
}
.gs-header p { color: #CFC6B4; font-size: 1rem; margin: 0; }
.gs-divider {
  width: 80px; height: 2px; margin: 1rem auto 0;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
}
.gs-note { text-align: center; color: #8E8778; font-size: 0.8rem; margin-top: 0.6rem; }

/* 탭 */
[data-testid="stTabs"] [data-baseweb="tab-list"] { justify-content: center; }

/* 미리보기 */
.st-key-preview { align-items: center; }
.st-key-preview [data-testid="stImage"] { margin: 0 auto; }
.st-key-preview img {
  max-width: min(350px, 100%) !important;
  height: auto !important;
  border-radius: 12px;
  border: 2px solid var(--gold);
  box-shadow: 0 6px 24px rgba(0,0,0,0.35);
}
.st-key-preview [data-testid="stCaptionContainer"] { text-align: center; }

/* 금색 버튼 */
[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #B8901C, var(--gold-soft)) !important;
  color: var(--ink) !important;
  border: none !important;
  font-weight: 700;
  font-size: 1.1rem;
  padding: 0.7rem 0;
  letter-spacing: 0.05em;
}
[data-testid="stBaseButton-primary"] p { color: var(--ink) !important; font-weight: 700; }
[data-testid="stBaseButton-primary"]:disabled { opacity: 0.4; }

/* 결과 카드 (한지 느낌) */
.st-key-result-card {
  background: var(--hanji);
  border: 1px solid var(--hanji-line) !important;
  border-radius: 16px;
  padding: 1.6rem 1.6rem 1rem;
  box-shadow: 0 10px 32px rgba(0,0,0,0.4);
}
.st-key-result-card * { color: var(--hanji-text); }
.st-key-result-card h2 {
  font-family: 'Nanum Myeongjo', serif;
  color: #7A5A0C !important;
  font-size: 1.35rem;
  border-bottom: 1px solid var(--hanji-line);
  padding-bottom: 0.35rem;
  margin-top: 1.2rem;
}
.st-key-result-card h3 { font-size: 1.05rem; margin-top: 0.6rem; }
.st-key-result-card [data-testid="stHeadingActionElements"] { display: none; }

/* 푸터 */
.gs-footer {
  text-align: center; color: #6F6A60; font-size: 0.78rem;
  margin-top: 3rem; padding-top: 1rem;
  border-top: 1px solid rgba(201,162,39,0.2);
}

/* 모바일 */
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; padding-top: 1.5rem; }
  .gs-header h1 { font-size: 2rem; }
  .gs-header .gs-icon { font-size: 2.4rem; }
  .st-key-result-card { padding: 1.1rem 1rem 0.6rem; }
  .st-key-result-card h2 { font-size: 1.2rem; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_header():
    """제목, 부제, 면책 문구를 보여준다."""
    st.markdown(
        f"""
<div class="gs-header">
  <div class="gs-icon">🔮</div>
  <h1>AI 관상가</h1>
  <p>얼굴에 새겨진 당신의 운명을 읽어드립니다</p>
  <div class="gs-divider"></div>
  <div class="gs-note">{DISCLAIMER}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_footer():
    """하단 면책 문구."""
    st.markdown(
        f'<div class="gs-footer">🔮 AI 관상가 · {DISCLAIMER}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- 상태 / 흐름

def digest_of(uploaded_file):
    """업로드 파일 내용의 해시. 파일이 없으면 None."""
    return hashlib.sha256(uploaded_file.getvalue()).hexdigest() if uploaded_file else None


def pick_latest_input(uploaded, captured):
    """업로드/카메라 중 가장 최근에 바뀐 입력을 고른다. (카메라 사진이 업로드를 계속 가리는 문제 방지)"""
    sources = {"upload": uploaded, "camera": captured}
    for name, file in sources.items():
        digest = digest_of(file)
        if st.session_state.get(f"last_{name}") != digest:
            st.session_state[f"last_{name}"] = digest
            if digest:
                st.session_state["active_source"] = name
    return sources.get(st.session_state.get("active_source")) or uploaded or captured


def get_input_file():
    """업로드/카메라 탭을 그리고, 가장 최근에 입력된 파일을 돌려준다."""
    version = st.session_state.get("input_version", 0)
    upload_tab, camera_tab = st.tabs(["📁 사진 업로드", "📷 카메라 촬영"])
    with upload_tab:
        uploaded = st.file_uploader(
            "얼굴이 잘 보이는 정면 사진을 올려 주세요. (JPG, PNG, WEBP · 최대 10MB)",
            type=ALLOWED_TYPES,
            key=f"uploader_{version}",
        )
    with camera_tab:
        captured = st.camera_input("카메라로 얼굴을 촬영하세요.", key=f"camera_{version}")
    return pick_latest_input(uploaded, captured)


def clear_outputs():
    """분석 결과와 안내 메시지를 지운다."""
    st.session_state.pop("result", None)
    st.session_state.pop("notice", None)


def reset_input():
    """입력 위젯과 결과를 모두 초기화한다. (위젯 key를 바꿔 새 위젯으로 만든다)"""
    st.session_state["input_version"] = st.session_state.get("input_version", 0) + 1
    clear_outputs()
    for key in ("image_digest", "last_upload", "last_camera", "active_source"):
        st.session_state.pop(key, None)


def reset_result_if_changed(data):
    """입력 이미지가 바뀌면 이전 분석 결과를 지운다."""
    digest = hashlib.sha256(data).hexdigest() if data else None
    if st.session_state.get("image_digest") != digest:
        st.session_state["image_digest"] = digest
        clear_outputs()


def check_usage_limit():
    """세션·전체 사용량 제한을 확인하고, 통과하면 횟수를 올린다. 막히면 안내 문구를 돌려준다."""
    now = time.time()
    used = st.session_state.get("analysis_count", 0)
    if used >= SESSION_LIMIT:
        return f"한 번 접속에 최대 {SESSION_LIMIT}번까지 관상을 볼 수 있습니다. 잠시 뒤에 다시 이용해 주세요."
    wait = COOLDOWN_SECONDS - (now - st.session_state.get("last_analysis_at", 0))
    if wait > 0:
        return f"너무 빠르게 요청했습니다. {int(wait) + 1}초 뒤에 다시 시도해 주세요."

    try:
        daily_limit = int(get_secret("DAILY_LIMIT", DEFAULT_DAILY_LIMIT))
    except (TypeError, ValueError):
        daily_limit = DEFAULT_DAILY_LIMIT
    counter = get_daily_counter()
    today = datetime.date.today().isoformat()
    with counter["lock"]:
        if counter["date"] != today:
            counter["date"], counter["count"] = today, 0
        if counter["count"] >= daily_limit:
            return "오늘 준비된 관상 풀이가 모두 소진되었습니다. 내일 다시 찾아 주세요. 🙏"
        counter["count"] += 1

    st.session_state["analysis_count"] = used + 1
    st.session_state["last_analysis_at"] = now
    return None


def run_analysis(api_key, model, jpeg_bytes):
    """분석을 요청한 뒤 결과(카드) 또는 안내(경고)를 session_state에 저장하고, 오류는 바로 표시한다."""
    clear_outputs()
    blocked = check_usage_limit()
    if blocked:
        st.warning(blocked)
        return
    try:
        result = analyze_face(get_client(api_key), model, encode_image(jpeg_bytes))
    except openai.AuthenticationError:
        st.error("API 키가 올바르지 않습니다. `.env` 또는 Streamlit Secrets의 `OPENAI_API_KEY`를 확인해 주세요.")
        return
    except openai.PermissionDeniedError:
        st.error("이 API 키로는 해당 모델을 사용할 권한이 없습니다. OpenAI 계정 설정을 확인해 주세요.")
        return
    except openai.RateLimitError:
        st.error("요청이 너무 많거나 사용 한도를 넘었습니다. 잠시 후 다시 시도하거나 OpenAI 사용량을 확인해 주세요.")
        return
    except (openai.APIConnectionError, openai.APITimeoutError):
        st.error("OpenAI 서버에 연결하지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도해 주세요.")
        return
    except (openai.BadRequestError, openai.NotFoundError):
        st.error(f"요청이 거절되었습니다. 이미지가 올바른지, 모델 이름(`{model}`)이 이미지 입력을 지원하는지 확인해 주세요.")
        return
    except openai.APIError:
        st.error("OpenAI 서버에서 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
        return
    except Exception:
        st.error("분석 중 알 수 없는 오류가 발생했습니다. 다른 사진으로 다시 시도해 주세요.")
        return

    if not result:
        st.error("관상 풀이 결과를 받지 못했습니다. 다시 시도해 주세요.")
    elif result.startswith(NO_FACE_PREFIX) or result == REFUSAL_MESSAGE:
        # 풀이가 아닌 안내 문구는 결과 카드/저장 버튼 없이 경고로만 보여준다
        st.session_state["notice"] = result
    else:
        st.session_state["result"] = result


def render_result(result):
    """결과 카드와 다운로드/다시 보기 버튼을 그린다."""
    with st.container(border=True, key="result-card"):
        st.markdown(result)

    col_download, col_reset = st.columns(2)
    with col_download:
        st.download_button(
            "📥 결과 저장 (.txt)",
            data=result,
            file_name="관상_결과.txt",
            mime="text/plain",
            on_click="ignore",
            width="stretch",
        )
    with col_reset:
        st.button("🔄 다른 사진으로 다시 보기", on_click=reset_input, width="stretch")


def main():
    inject_css()
    render_header()

    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        st.error(
            "OpenAI API 키가 설정되지 않았습니다.\n\n"
            "- **로컬**: 프로젝트 폴더의 `.env` 파일에 `OPENAI_API_KEY=sk-...` 를 추가하세요.\n"
            "- **Streamlit Cloud**: 앱 설정 → Secrets에 `OPENAI_API_KEY = \"sk-...\"` 를 추가하세요."
        )
        render_footer()
        st.stop()
    model = get_secret("OPENAI_MODEL") or DEFAULT_MODEL

    input_file = get_input_file()
    data = input_file.getvalue() if input_file else None

    if data and len(data) > MAX_FILE_BYTES:
        st.warning("파일이 10MB를 넘습니다. 더 작은 사진을 올려 주세요.")
        data = None

    jpeg_bytes = None
    if data:
        try:
            jpeg_bytes = prepare_image(data)
        except ImageTooLargeError:
            st.error("사진 해상도가 너무 큽니다. 2,500만 화소 이하의 사진을 올려 주세요.")
            data = None
        except Exception:
            st.error("이미지를 읽을 수 없습니다. JPG, PNG, WEBP 형식의 올바른 사진인지 확인해 주세요.")
            data = None

    reset_result_if_changed(data)

    if jpeg_bytes is not None:
        with st.container(key="preview"):
            st.image(jpeg_bytes, caption="분석할 사진", width=350)
            st.caption(f"🔒 {PRIVACY_NOTICE}")

    if st.button("🔮 관상 보기", type="primary", disabled=not data, width="stretch"):
        with st.spinner("도사가 관상을 살펴보는 중입니다..."):
            run_analysis(api_key, model, jpeg_bytes)

    if st.session_state.get("notice"):
        st.warning(st.session_state["notice"])
    if st.session_state.get("result"):
        render_result(st.session_state["result"])

    render_footer()


main()
