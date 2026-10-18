import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

TOPVIEW_API_KEY = os.getenv("TOPVIEW_API_KEY", "")
TOPVIEW_UID = os.getenv("TOPVIEW_UID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FFMPEG_PATH = os.getenv(
    "FFMPEG_PATH",
    r"C:\Users\PC\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe",
)
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", r"C:\Users\PC\Downloads\shorts_output"))

TOPVIEW_BASE = "https://api.topview.ai"
TOPVIEW_GET_CREDIT         = f"{TOPVIEW_BASE}/user/credit/detail"
TOPVIEW_UPLOAD_CRED        = f"{TOPVIEW_BASE}/v1/upload/credential"
TOPVIEW_UPLOAD_CHECK       = f"{TOPVIEW_BASE}/v1/upload/check"
TOPVIEW_IMAGE2VIDEO_SUBMIT = f"{TOPVIEW_BASE}/v2/common_task/image2video/task/submit"
TOPVIEW_IMAGE2VIDEO_QUERY  = f"{TOPVIEW_BASE}/v2/common_task/image2video/task/query"
TOPVIEW_OMNI_SUBMIT        = f"{TOPVIEW_BASE}/v1/common_task/omni_reference/task/submit"
TOPVIEW_OMNI_QUERY         = f"{TOPVIEW_BASE}/v1/common_task/omni_reference/task/query"
TOPVIEW_LIST_VOICES        = f"{TOPVIEW_BASE}/v1/voice/query"
TOPVIEW_VOICE_SUBMIT       = f"{TOPVIEW_BASE}/v1/voice/text2voice/task/submit"
TOPVIEW_VOICE_QUERY        = f"{TOPVIEW_BASE}/v1/voice/text2voice/task/query"
