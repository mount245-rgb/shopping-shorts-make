"""Topview REST API wrapper."""
import time
import mimetypes
from pathlib import Path

import requests
import config


def _headers():
    h = {"Authorization": f"Bearer {config.TOPVIEW_API_KEY}"}
    if config.TOPVIEW_UID:
        h["Topview-Uid"] = config.TOPVIEW_UID
    return h


def upload_file(file_path) -> str:
    """로컬 파일을 Topview S3에 업로드하고 fileId를 반환."""
    file_path = Path(file_path)
    suffix = file_path.suffix.lstrip(".")
    mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    r = requests.get(
        config.TOPVIEW_UPLOAD_CRED,
        headers=_headers(),
        params={"format": suffix},
    )
    r.raise_for_status()
    data = r.json()
    result = data.get("result", data)
    upload_url = result["uploadUrl"]
    file_id = result["fileId"]

    with open(file_path, "rb") as f:
        put_r = requests.put(upload_url, data=f, headers={"Content-Type": mime})
        put_r.raise_for_status()

    r2 = requests.get(
        config.TOPVIEW_UPLOAD_CHECK,
        headers=_headers(),
        params={"fileId": file_id},
    )
    r2.raise_for_status()
    return file_id


def _extract_task_id(data: dict) -> str:
    """응답에서 taskId 추출 — 최상위 또는 result/data 래퍼 모두 지원."""
    tid = data.get("taskId")
    if not tid:
        inner = data.get("result", data.get("data", {}))
        if isinstance(inner, dict):
            tid = inner.get("taskId")
    if not tid:
        raise ValueError(f"taskId를 찾을 수 없음. 응답: {data}")
    return tid


def generate_video_image_to_video(prompt: str, first_frame_file_id: str, duration: int = 4) -> str:
    payload = {
        "model": "Wan 3.0 Prime",
        "prompt": prompt,
        "resolution": 480,
        "duration": duration,
        "generatingCount": 1,
        "firstFrameFileId": first_frame_file_id,
    }
    r = requests.post(config.TOPVIEW_IMAGE2VIDEO_SUBMIT, headers=_headers(), json=payload)
    r.raise_for_status()
    return _extract_task_id(r.json())


def generate_video_omni_ref(prompt: str, product_file_id: str, duration: int = 4) -> str:
    payload = {
        "model": "Wan 3.0 Prime",
        "prompt": f"<<<Image1>>> {prompt}",
        "aspectRatio": "9:16",
        "resolution": 480,
        "duration": duration,
        "generatingCount": 1,
        "inputImages": [{"fileId": product_file_id, "name": "Image1"}],
    }
    r = requests.post(config.TOPVIEW_OMNI_SUBMIT, headers=_headers(), json=payload)
    r.raise_for_status()
    return _extract_task_id(r.json())


def poll_task(task_id: str, task_type: str = "image_to_video", timeout: int = 900) -> str:
    """완료될 때까지 폴링, 다운로드 URL 반환."""
    query_url = config.TOPVIEW_IMAGE2VIDEO_QUERY if task_type == "image_to_video" else config.TOPVIEW_OMNI_QUERY

    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(query_url, headers=_headers(), params={"taskId": task_id})
        r.raise_for_status()
        data = r.json()
        # status는 최상위 또는 result 안에 있을 수 있음
        inner = data.get("result") if isinstance(data.get("result"), dict) else {}
        status = data.get("status") or inner.get("status")
        if status == "success":
            videos = data.get("videos") or inner.get("videos", [])
            if not videos:
                raise RuntimeError(f"videos 키가 없음. 응답: {data}")
            return videos[0].get("filePath") or videos[0].get("url", "")
        if status in ("fail", "failed", "error"):
            raise RuntimeError(f"Task {task_id} failed: {data}")
        time.sleep(15)
    raise TimeoutError(f"Task {task_id} timed out")


def download_file(url: str, dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
    return dest


def list_korean_voices() -> list:
    r = requests.get(config.TOPVIEW_LIST_VOICES, headers=_headers(), params={"language": "ko"})
    r.raise_for_status()
    data = r.json()
    voices = data.get("voices") or data.get("result", {}).get("voices") or data.get("data", {}).get("voices") or []
    # language 필터 결과가 빈 경우 전체 조회 후 ko 포함 항목만 추출
    if not voices:
        r2 = requests.get(config.TOPVIEW_LIST_VOICES, headers=_headers())
        r2.raise_for_status()
        d2 = r2.json()
        all_v = d2.get("voices") or d2.get("result", {}).get("voices") or d2.get("data", {}).get("voices") or []
        voices = [v for v in all_v if "ko" in str(v.get("language", v.get("locale", ""))).lower()
                  or "korean" in str(v.get("name", "")).lower()]
        if not voices:
            voices = all_v  # 필터 안 되면 전체 반환
    return voices


def generate_voice(voice_id: str, text: str, speed: float = 1.0) -> str:
    r = requests.post(
        config.TOPVIEW_VOICE_SUBMIT,
        headers=_headers(),
        json={"voiceId": voice_id, "voiceText": text, "voiceSpeed": speed},
    )
    r.raise_for_status()
    data = r.json()

    # immediate URL (no async task)
    immediate = (data.get("audioUrl")
                 or data.get("result", {}).get("audioUrl")
                 or data.get("data", {}).get("audioUrl"))
    if immediate:
        return immediate

    task_id = (data.get("taskId")
               or data.get("result", {}).get("taskId")
               or data.get("data", {}).get("taskId"))
    if not task_id:
        raise RuntimeError(f"taskId 없음. 응답: {data}")

    deadline = time.time() + 180
    while time.time() < deadline:
        r2 = requests.get(
            config.TOPVIEW_VOICE_QUERY,
            headers=_headers(),
            params={"taskId": task_id},
        )
        r2.raise_for_status()
        d = r2.json()
        inner = d.get("result") if isinstance(d.get("result"), dict) else {}
        status = d.get("status") or inner.get("status")
        if status == "success":
            audio_url = (d.get("audioUrl")
                         or inner.get("audioUrl")
                         or inner.get("voice", {}).get("demoAudioUrl")
                         or inner.get("voice", {}).get("audioUrl")
                         or d.get("url", ""))
            if not audio_url:
                raise RuntimeError(f"오디오 URL 없음. 응답: {d}")
            return audio_url
        if status in ("fail", "failed", "error"):
            raise RuntimeError(f"Voice task {task_id} failed: {d}")
        time.sleep(5)
    raise TimeoutError("Voice generation timed out")


def get_credit() -> float:
    r = requests.get(config.TOPVIEW_GET_CREDIT, headers=_headers())
    r.raise_for_status()
    data = r.json()
    result = data.get("result", data.get("data", data))
    return float(result.get("remainCredit", result.get("balance", result.get("credit", 0))))
