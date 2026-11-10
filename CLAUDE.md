# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI 관상가 is a Streamlit app: the user uploads or takes a face photo, and an OpenAI vision model writes a face reading (관상) of it in Korean. The whole app lives in `app.py`. It will be deployed from GitHub to Streamlit Community Cloud.

- `prd.md` is the spec. Its section IDs (F1–F8, 6장 prompt, 7.3 keys, 7.4 privacy, 7.5 usage limits, 8장 UI) are the acceptance criteria. Keep it in sync when behavior changes.
- `prompts.md` holds the four build-stage prompts ("N단계"). All four are done. Review items deliberately left open: Streamlit's English error text for >10MB and GIF uploads, Markdown symbols in the `.txt` download, and tab centering.
- `.env` holds the user's real `OPENAI_API_KEY`. Never print its contents or commit it. To check it, mask the values (`sed -E 's/=.*/=<hidden>/' .env`).
- The user writes in Korean. Reply in Korean, and keep all UI text and model output in Korean.

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py                                              # http://localhost:8501
streamlit run app.py --server.headless true --server.port 8501   # background, for Playwright
```

Restart the server after editing `.streamlit/config.toml`, because theme and `maxUploadSize` are read only at startup. Edits to `app.py` are picked up on the next rerun.

There is no test suite or linter. Verify changes this way:

- **Function-level checks.** Exec `app.py` without its last line to load the functions without rendering the UI:
  `src = open("app.py", encoding="utf-8").read().replace("\nmain()\n", "\n"); ns = {}; exec(compile(src, "app.py", "exec"), ns)`.
  Swap `ns["st"]` for a fake with a dict `session_state` to test session logic such as `pick_latest_input`. On this Windows console, set `PYTHONIOENCODING=utf-8` before printing model output, which contains emoji.
- **Browser checks.** Use the Playwright MCP tools. They can only upload files from inside the project folder, so test images live in `.playwright-mcp/img/` (gitignored): `plain.jpg` (no face), `dl/face.jpg` (public-domain portrait), `transparent.png`, `big.jpg`, `broken.jpg`, `huge.png` (>10MB), `bomb.png` (144MP, 434KB), `sample.gif`, `UPPER.JPG`.
- **Error paths without touching `.env`.** `load_dotenv()` doesn't override variables that are already set, so start extra instances on other ports with env overrides: `OPENAI_API_KEY=sk-invalid` (auth error), `OPENAI_API_KEY=` (missing-key screen), `DAILY_LIMIT=0` (daily cap, no API call made).
- **Real API calls cost money.** Keep them to a few per verification. The app enforces a 10-second cooldown between analyses in a session.

## Architecture

Flow inside `main()`:
input tabs → `pick_latest_input` → size check → `prepare_image` (cached) → preview → button → `check_usage_limit` → `analyze_face` → result kept in `st.session_state` and rendered as either a result card or a warning.

Couplings and constraints that aren't obvious from a single function:

- **Secrets in two places.** Locally, the key comes from `.env` via `python-dotenv`. On Streamlit Cloud it comes from `st.secrets`. `get_secret` checks `st.secrets` first and must swallow the exception raised when no `secrets.toml` exists. Configurable keys are `OPENAI_API_KEY`, `OPENAI_MODEL` and `DAILY_LIMIT`. `.gitignore` excludes `.env` and `.streamlit/secrets.toml` but must not exclude `.streamlit/config.toml` (theme and upload limit), which has to be deployed.
- **Model choice.** The default is `gpt-5.4-mini`. Don't go back to `gpt-4o-mini`: it refuses face readings, and because of the no-face rule it disguises the refusal as "얼굴을 찾기 어렵습니다" even on clear face photos. gpt-5 models count reasoning tokens against `max_completion_tokens`, so keep `MAX_OUTPUT_TOKENS` generous (4000).
- **Prompt and code are coupled.** `SYSTEM_PROMPT` dictates exact heading text and order (첫인상 → 부위별 풀이 → 운세 → 총평 → 동물상) and the exact no-face sentence. `run_analysis` detects that sentence through `NO_FACE_PREFIX`, and the refusal text through `REFUSAL_MESSAGE`, to show a warning instead of a result card. If you reword those sentences, update the constants too. The no-face reply must stay limited to images with no face at all.
- **Images stay in memory and are bounded.** `load_image` reads the pixel count from the header before decoding and rejects anything over `MAX_PIXELS`, since a ~400KB PNG once decoded to about 1.2GB. It uses `draft()` for JPEG and resizes in place, with no `copy()`. `prepare_image` is cached with `st.cache_data`, so reruns don't reprocess the same bytes. Nothing is written to disk.
- **Rerun safety.** Streamlit reruns the whole script on every interaction. The API is called only on the button click. Results are cleared when the input digest changes (`reset_result_if_changed`). "다시 보기" (`reset_input`) bumps `input_version`, which is part of the widget keys and gives fresh uploader and camera widgets.
- **Usage limits.** `check_usage_limit` applies a per-session cap and cooldown in `session_state`, plus an app-wide daily counter kept in a `cache_resource` dict with a lock. The daily counter resets on restart, and the session caps reset on a page refresh. The real cost ceiling is the OpenAI dashboard budget.
- **CSS hooks.** All styling lives in `inject_css()`. It targets `data-testid` selectors and the `st-key-<key>` classes that Streamlit adds to keyed containers (`result-card`, `preview`). Renaming those container keys silently breaks the styling.
