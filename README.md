# 🔮 AI 관상가

얼굴 사진을 올리면 OpenAI 이미지 분석 모델이 전통 관상학 용어로 관상을 풀이해 주는 Streamlit 웹앱입니다.

> 본 결과는 재미를 위한 것이며 과학적 근거가 없습니다.
> 업로드한 사진은 저장되지 않으며, 분석을 위해 OpenAI로 전송됩니다.

## 로컬 실행

```bash
# 1. 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. 패키지 설치
pip install -r requirements.txt

# 3. .env 작성 (.env.example 복사 후 키 입력)
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux

# 4. 실행
streamlit run app.py
```

`.env` 예시:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
```

## Streamlit Community Cloud 배포

1. 이 저장소를 GitHub에 push합니다. (`.env`는 `.gitignore`로 제외되어 올라가지 않습니다.)
2. [share.streamlit.io](https://share.streamlit.io)에 로그인 → **New app**
3. 저장소, 브랜치, Main file path(`app.py`)를 선택합니다.
4. **Advanced settings → Secrets**에 아래 내용을 입력합니다.

   ```toml
   OPENAI_API_KEY = "sk-..."
   OPENAI_MODEL = "gpt-5.4-mini"
   DAILY_LIMIT = 200   # 선택: 앱 전체 하루 분석 횟수 상한 (기본 200)
   ```

5. **Deploy**를 누르면 공개 URL이 생성됩니다.

앱은 `st.secrets`를 먼저 확인하고, 없으면 `.env`(환경변수)에서 키를 읽습니다.

> 공개 URL은 누구나 접속할 수 있어 API 비용이 발생합니다. 앱에는 세션당 10회, 10초 간격, 하루 `DAILY_LIMIT`회 제한이 있지만,
> [OpenAI 대시보드](https://platform.openai.com/settings/organization/limits)에서 **월 예산 한도**도 함께 설정하는 것을 권장합니다.
