# AI 관상가 — 단계별 개발 프롬프트

> 각 단계 프롬프트를 순서대로 Claude Code에 붙여 넣어 실행하세요.
> 한 단계가 끝나면 결과를 확인한 뒤 다음 단계로 넘어갑니다.

---

## 1단계: 기본 뼈대 작성

```
prd.md를 읽고, PRD 7.1의 프로젝트 구조대로 기본 뼈대를 만들어줘.

만들 파일:
1. requirements.txt — streamlit, openai, python-dotenv, Pillow
2. .env.example — OPENAI_API_KEY=, OPENAI_MODEL=gpt-4o-mini (실제 키는 넣지 말 것)
3. .gitignore — .env, .streamlit/secrets.toml, __pycache__/, *.pyc, .venv/, venv/ 포함
4. app.py — 아래 내용만 들어간 최소 실행 가능한 뼈대
   - st.set_page_config(page_title="AI 관상가", page_icon="🔮", layout="centered")
   - load_dotenv() 호출
   - get_secret(name, default) 함수: st.secrets → os.getenv 순서로 읽고, secrets.toml이 없어서 생기는 예외는 무시
   - OPENAI_API_KEY가 없으면 st.error로 설정 방법(.env / Streamlit Secrets)을 안내하고 st.stop()
   - 제목, 서비스 설명, 면책 문구("본 결과는 재미를 위한 것이며 과학적 근거가 없습니다")
   - 아직 구현하지 않은 기능 자리는 함수만 만들어 두기: load_image(), resize_image(), encode_image(), analyze_face()
5. README.md — 프로젝트 소개, 로컬 실행 방법(venv 생성, pip install, .env 작성, streamlit run app.py), Streamlit Cloud 배포 방법(Secrets 설정 포함)

조건:
- .env 파일은 만들지 말고 .env.example만 만들 것 (실제 키는 내가 직접 넣음)
- 다 만든 뒤 pip install -r requirements.txt 하고 streamlit run app.py가 오류 없이 뜨는지 확인해줘
- 마지막에 git init 하고 .env가 git status에 나오지 않는지 확인해줘 (커밋은 하지 말 것)
```

---

## 2단계: 주요 기능 추가

```
prd.md의 5장(기능 요구사항)과 6장(AI 프롬프트 설계)을 기준으로 app.py에 주요 기능을 구현해줘.

구현할 기능:
1. [F1, F2] 입력: st.tabs로 "📁 사진 업로드" / "📷 카메라 촬영" 탭 구성
   - file_uploader: jpg, jpeg, png, webp만 허용
   - 10MB 초과 파일은 st.warning으로 안내하고 분석하지 않음
   - 두 탭 중 입력된 이미지를 하나로 선택 (카메라 입력이 있으면 우선)
2. [F3] 미리보기: 선택된 이미지를 st.image로 표시
3. 이미지 전처리:
   - Pillow로 열고, EXIF 회전 보정(ImageOps.exif_transpose)
   - RGBA/P 모드는 RGB로 변환
   - 긴 변 1024px 이하로 축소
   - JPEG로 다시 저장 후 base64 인코딩 → data:image/jpeg;base64,... 형식
   - 이미지는 디스크에 저장하지 말고 메모리(BytesIO)에서만 처리
4. [F4] analyze_face(): OpenAI 공식 Python SDK로 이미지+텍스트를 함께 보내기
   - 모델은 get_secret("OPENAI_MODEL", "gpt-4o-mini")
   - PRD 6장의 System Prompt를 그대로 사용 (결과 형식: 첫인상 요약 → 부위별 풀이 → 운세(재물/애정/직업/건강) → 총평 및 조언 → 닮은 동물상)
   - 최대 출력 토큰 약 1500, 이미지 detail은 "auto"
   - OpenAI 클라이언트는 @st.cache_resource로 한 번만 생성
5. [F5, F6] "🔮 관상 보기" 버튼
   - 이미지가 없으면 disabled
   - 누르면 st.spinner("관상을 보는 중입니다...") 표시 후 결과를 st.markdown으로 출력
   - 결과는 st.session_state에 저장해서 다시 그려도 사라지지 않게 하고, 새 이미지가 올라오면 이전 결과 초기화
6. [F7] 오류 처리 — 모든 오류는 앱이 멈추지 않고 한국어로 안내
   - openai.AuthenticationError → API 키 확인 안내
   - openai.RateLimitError → 잠시 후 다시 시도 / 사용량 확인 안내
   - openai.APIConnectionError, APITimeoutError → 네트워크 안내
   - openai.BadRequestError → 이미지 또는 모델 설정 확인 안내
   - PIL.UnidentifiedImageError → 이미지 형식 오류 안내
   - 응답 내용이 비어 있으면 다시 시도 안내
7. [F8] 이미지 아래에 "사진은 저장되지 않으며 분석을 위해 OpenAI로 전송됩니다" 안내 표시

조건:
- API 키, 모델명은 절대 코드에 직접 쓰지 말 것 (기본 모델명 문자열만 예외)
- 함수별로 짧은 docstring 추가
- 구현 후 streamlit run app.py로 실행해 오류 없이 뜨는지 확인해줘
- 내가 .env에 키를 넣어 두었다면 샘플 얼굴 이미지로 실제 분석이 되는지도 확인해줘
```

---

## 3단계: UI 디자인

```
prd.md 8장(UI/UX 요구사항)을 기준으로 app.py의 화면을 다듬어줘. 기능 로직은 바꾸지 말고 화면만 개선해.

디자인 방향: 동양적·신비로운 분위기의 "관상가의 방" 느낌
- 색: 짙은 남색/먹색 배경 계열 + 금색 포인트(#C9A227 근처), 한지 느낌의 밝은 카드
- 글꼴: Google Fonts의 한글 글꼴(예: 제목은 Nanum Myeongjo, 본문은 Noto Sans KR)을 st.markdown(unsafe_allow_html=True)로 불러오기

구현할 것:
1. .streamlit/config.toml에 테마 설정 (primaryColor, backgroundColor, secondaryBackgroundColor, textColor, font)
   - 주의: .gitignore에서 .streamlit/ 폴더 전체가 아니라 secrets.toml만 제외되는지 확인할 것
2. 상단 헤더: 🔮 아이콘 + "AI 관상가" 제목 + 한 줄 부제 ("얼굴에 새겨진 당신의 운명을 읽어드립니다")
3. 면책 문구와 개인정보 안내는 작고 눈에 덜 띄게 st.caption 또는 작은 카드로
4. 입력 영역: 탭 + 이미지 미리보기를 가운데 정렬, 미리보기 최대 너비 약 350px
5. "관상 보기" 버튼: 가로 전체 너비(use_container_width=True), 금색 강조
6. 결과 영역:
   - 결과를 카드(테두리, 둥근 모서리, 여백) 안에 표시
   - 부위별 풀이 섹션 제목에 이모지 사용 (예: 🧠 이마, 👁 눈, 👃 코, 👄 입 등) — System Prompt에서 이 형식을 요청하도록 프롬프트도 함께 수정
   - 결과 아래에 "다른 사진으로 다시 보기" 버튼 (session_state 초기화)
   - 결과 텍스트를 .txt로 받을 수 있는 st.download_button
7. 하단 푸터: 면책 문구 한 줄
8. 모바일 화면(폭 약 375px)에서도 가로 스크롤 없이 보이도록 CSS 조정

조건:
- 커스텀 CSS는 한 곳(함수 하나)에 모아서 관리
- Streamlit 내부 클래스명(.css-xxxx 같은 자동 생성 클래스)에 의존하지 말고, data-testid 선택자나 직접 만든 클래스 사용
- 다 만든 뒤 실행해서 데스크톱/모바일 폭 모두 화면이 깨지지 않는지 확인해줘
```

---

## 4단계: PRD 준수 여부 및 버그 검토 (Playwright 활용)

```
지금까지 만든 앱이 prd.md대로 개발되었는지, 문제나 버그가 없는지 자세히 검토해줘.
Playwright MCP 브라우저 도구를 사용해서 실제로 앱을 띄워 확인해야 해.

[준비]
1. streamlit run app.py --server.headless true --server.port 8501 을 백그라운드로 실행
2. 테스트용 이미지 준비 (scratchpad 등 프로젝트 밖 임시 폴더에 생성):
   - 정상 얼굴 사진 1장 (내가 제공하지 않았다면 물어볼 것)
   - 얼굴이 없는 이미지 (예: Pillow로 만든 단색/풍경 이미지)
   - PNG(투명 배경), 큰 이미지(4000px 이상), 10MB 초과 파일
   - 확장자만 .jpg인 손상된 파일 (텍스트 파일 이름 변경)

[Playwright 검사 항목]
A. 화면 / UI
   - http://localhost:8501 접속 후 스냅샷 + 스크린샷
   - 제목, 부제, 면책 문구, 개인정보 안내가 보이는지
   - 이미지 없을 때 "관상 보기" 버튼이 비활성화인지
   - 375px(모바일) / 1280px(데스크톱)으로 크기 조절 후 스크린샷, 가로 스크롤·겹침 여부
   - 브라우저 콘솔 에러 확인
B. 기능
   - 정상 사진 업로드 → 미리보기 → 버튼 클릭 → 결과에 PRD 5.2의 모든 섹션(첫인상, 부위별 풀이, 재물/애정/직업/건강운, 총평, 동물상, 재미 문구)이 있는지
   - 결과가 나온 뒤 다른 위젯을 건드려도 결과가 유지되는지, 새 사진을 올리면 초기화되는지
   - "다른 사진으로 다시 보기", 다운로드 버튼 동작
   - 얼굴 없는 이미지 → "얼굴을 찾기 어렵습니다" 류의 안내가 나오는지
   - 10MB 초과 / 손상 파일 / 허용되지 않은 확장자 → 앱이 죽지 않고 한국어 안내가 나오는지
   - 큰 이미지, 투명 PNG도 정상 처리되는지
C. 오류 상황
   - 잘못된 API 키로 실행(.env를 직접 바꾸지 말고 환경변수 OPENAI_API_KEY=sk-invalid로 따로 실행) → 인증 오류 안내가 나오는지
   - API 키가 아예 없을 때 설정 안내 후 멈추는지

[코드 검토 항목]
- API 키·개인정보: 키 하드코딩 여부, .gitignore에 .env와 secrets.toml 포함 여부, 이미지가 디스크에 저장되는 곳이 있는지
- get_secret: 로컬(secrets.toml 없음)과 Streamlit Cloud 양쪽에서 동작하는지
- OpenAI SDK 사용법이 현재 버전에 맞는지, 모델이 이미지 입력을 지원하는지
- requirements.txt만으로 Streamlit Cloud에서 설치/실행 가능한지
- 예외 처리 누락, session_state 관련 버그, 불필요한 중복 API 호출(재실행 때마다 호출되는지)
- System Prompt가 PRD 6장의 금지 규칙(비하 표현, 민감 정보 추정 금지)을 지키는지

[결과 보고]
1. PRD 요구사항 체크리스트 표: ID(F1~F8, 7.3, 7.4, 8장 등) | 충족 여부(✅/⚠️/❌) | 근거(스크린샷 또는 코드 위치 파일:줄)
2. 발견한 버그/문제 목록: 심각도(높음/중간/낮음) | 재현 방법 | 원인 | 수정 제안
3. 스크린샷 파일 경로 목록
4. 바로 고칠 수 있는 문제는 수정 전에 목록을 먼저 보여주고, 내가 승인하면 수정한 뒤 해당 항목만 다시 Playwright로 확인

주의:
- 실제 API 호출은 비용이 드니 정상 사진 분석은 2~3회 이내로 할 것
- 검사가 끝나면 streamlit 프로세스를 종료할 것
```
