# AI 기반 스마트 면접관

Python으로 구현한 면접 연습기입니다. 카메라·마이크로 실전처럼 연습하고, GPT 기반 피드백과 상세 리포트를 받을 수 있습니다.

## 기능

1. **카메라 실시간 연습** – MediaPipe로 얼굴 인식, 시선 유지 확인
2. **GPT 실시간 피드백** – 답변 후 말하기 속도, 논리성, 구체성 평가
3. **말하기 속도·논리성·구체성** – AI가 항목별 코멘트 제공
4. **점수·상세 리포트** – 질문별 점수와 마크다운 리포트 다운로드
5. **마이크 연습** – 브라우저 마이크로 실제 면접처럼 답변 녹음
6. **습관어 체크** – um, uh, 어, 음, 그, 저기 등 감지 및 피드백
7. **목소리 톤·자신감** – 텍스트 기반 톤/자신감 분석
8. **맞춤형 질문** – 지원 회사/직무 입력 → 예상 질문 자동 생성

## 설치

```bash
cd "c:\Users\user\Desktop\interview sample"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## .env 설정 (OpenAI API)

1. [OpenAI API Keys](https://platform.openai.com/api-keys)에서 API 키 발급
2. 프로젝트 폴더에 `.env` 파일 생성 후 아래 한 줄 추가:

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

`.env.example`을 복사한 뒤 `your_openai_api_key_here` 부분만 실제 키로 바꿔도 됩니다.

## 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 로 접속합니다.

## 사용 방법

1. **맞춤형 질문**: 왼쪽 사이드바에 지원 **회사명**, **직무** 입력 후 **예상 질문 생성** 클릭
2. **연습하기**:  
   - **연습하기** 탭에서 카메라로 얼굴 촬영(선택)  
   - 표시된 질문에 대해 **녹음 시작** → 답변 후 **녹음 종료**  
   - 음성 인식 및 AI 피드백(점수, 논리성, 구체성, 속도, 습관어, 톤/자신감) 확인
3. **세션 리포트**: **세션 리포트** 탭에서 평균 점수, 습관어 사용 횟수, 상세 리포트 확인 및 마크다운 다운로드
4. **질문만 생성**: **질문만 생성** 탭에서 회사/직무만 입력하고 예상 질문만 따로 생성 가능

## 폴더 구조

- `app.py` – Streamlit 메인 앱
- `config.py` – 환경 변수(.env) 로드
- `face_detector.py` – MediaPipe 얼굴 인식
- `speech_handler.py` – 마이크 녹음·음성 인식·습관어/속도 분석
- `ai_feedback.py` – OpenAI GPT 피드백·평가
- `question_generator.py` – 회사/직무 기반 질문 생성
- `report_generator.py` – 점수·상세 리포트 생성
- `requirements.txt` – 의존성
- `.env.example` – .env 예시

## GitHub 레포지토리 만들고 푸시하기

1. [GitHub](https://github.com/new)에서 **New repository**로 새 저장소 생성 (이름 예: `interview-sample`).
2. **Initialize with README**는 체크하지 않습니다 (이미 로컬에 코드가 있음).
3. 터미널에서 아래 실행 (`YOUR_USERNAME`, `REPO_NAME`을 본인 값으로 바꾸세요):

```bash
cd "c:\Users\user\Desktop\interview sample"
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git
git branch -M main
git push -u origin main
```

- GitHub CLI(`gh`)가 있다면: `gh repo create REPO_NAME --private --source=. --push` 로 한 번에 생성·푸시 가능합니다.

## 배포 (Vercel vs Streamlit)

- **이 프로젝트는 Streamlit(Python 서버) 앱**입니다. Vercel은 정적 사이트·Next.js·서버리스 함수 위주라 **Streamlit 앱을 그대로 올리기에는 적합하지 않습니다.**
- **권장: Streamlit Community Cloud** (무료, GitHub 연동)
  1. [share.streamlit.io](https://share.streamlit.io) 접속 후 GitHub 로그인.
  2. **New app** → 이 레포지토리 선택, Branch `main`, Main file path `app.py`.
  3. **Advanced settings**에서 Secrets에 `OPENAI_API_KEY` 추가.
  4. Deploy 후 제공되는 URL로 접속하면 됩니다.

- 그 외 **Railway**, **Render** 등에서도 Python 앱으로 배포 가능합니다 (빌드 명령: `pip install -r requirements.txt`, 실행: `streamlit run app.py --server.port $PORT`).

## 참고

- 음성 인식은 브라우저/Google API를 사용합니다. 한글 인식이 안 되면 영어로 답변해 보세요.
- 실제 면접 질문 수집(`collect_questions_placeholder`)은 현재 비어 있으며, 필요 시 크롤링·API로 확장할 수 있습니다.
