# 쇼핑 쇼츠 메이커

쿠팡/틱톡 상품 링크를 입력하면 AI가 스크립트를 생성하고 쇼츠 영상을 자동으로 만들어주는 앱입니다.

## 주요 기능

- 쿠팡/틱톡 상품 페이지 자동 스크래핑
- Claude AI로 쇼츠 스크립트 자동 생성
- Topview AI로 영상 자동 제작
- 한국어 나레이션 + 자막 자동 합성
- GUI 인터페이스 (더블클릭 실행)

## 설치 방법

```bash
# 저장소 클론
git clone https://github.com/mount245-rgb/shopping-shorts-make.git
cd shopping-shorts-make

# 가상환경 생성 (권장)
python -m venv venv
venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

## 환경 변수 설정

`.env.example`을 복사해서 `.env` 파일을 만들고 API 키를 입력합니다.

```
copy .env.example .env
```

`.env` 파일 내용:

```
TOPVIEW_API_KEY=여기에_Topview_API_키_입력
ANTHROPIC_API_KEY=여기에_Claude_API_키_입력
FFMPEG_PATH=C:\경로\ffmpeg.exe
OUTPUT_DIR=C:\Users\PC\Downloads\shorts_output
```

> **API 키 발급**
> - Topview API: https://www.topview.ai
> - Anthropic API: https://console.anthropic.com

## 실행

`쇼핑쇼츠_실행.bat` 파일을 더블클릭하거나:

```bash
python gui.py
```

## 프로젝트 구조

```
shopping-shorts-make/
├── gui.py              # GUI 인터페이스 (메인 화면)
├── main.py             # CLI 인터페이스
├── scraper.py          # 상품 정보 스크래핑
├── script_gen.py       # Claude AI 스크립트 생성
├── topview_client.py   # Topview AI API 연동
├── video_analyzer.py   # 영상 분석
├── ffmpeg_merge.py     # 영상/오디오 합성
├── srt_builder.py      # 자막 파일 생성
├── config.py           # 환경 변수 설정
├── requirements.txt
├── .env.example        # 환경 변수 예시
└── 쇼핑쇼츠_실행.bat   # 실행 파일 (Windows)
```

## 라이선스

MIT
