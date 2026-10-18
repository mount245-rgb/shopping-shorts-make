"""MP4 reference video analyzer — extracts frames and asks Claude for 3 ad concepts."""
import base64
import json
import re
import subprocess
import tempfile
from pathlib import Path

import anthropic
import config

_CONCEPT_SCHEMA = '[{"title":"컨셉명","hook":"초반3초후킹문구","style":"UGC리얼|감성비교|언박싱|문제해결","narration_tone":"톤설명","description":"컨셉전체설명"}]'

_SYSTEM = (
    "당신은 쇼핑 쇼츠 광고 기획 전문가입니다. "
    "제공된 정보를 분석해 광고티 없는 자연스러운 15초 쇼츠 컨셉 3가지를 JSON 배열로만 반환하세요. "
    f"반드시 이 스키마를 따르세요: {_CONCEPT_SCHEMA}"
)


def extract_frames(video_path: str, n: int = 5) -> list:
    """ffmpeg으로 영상에서 n개 프레임 추출 → 임시 디렉토리의 Path 리스트 반환."""
    tmp = Path(tempfile.mkdtemp())
    out_pat = str(tmp / "frame_%03d.jpg")
    cmd = [
        config.FFMPEG_PATH, "-y", "-i", str(video_path),
        "-vf", "fps=1/2", "-frames:v", str(n), "-q:v", "3", out_pat,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    frames = sorted(tmp.glob("frame_*.jpg"))
    if not frames:
        raise RuntimeError(
            f"ffmpeg 프레임 추출 실패 (returncode={result.returncode})\n"
            + result.stderr.decode("utf-8", errors="replace")[-500:]
        )
    return frames[:n]


def analyze_video(video_path: str, product_name: str = "") -> list:
    """MP4 영상을 분석해 쇼츠 광고 컨셉 3개를 반환."""
    frames = extract_frames(video_path)
    content = []
    for f in frames:
        b64 = base64.standard_b64encode(Path(f).read_bytes()).decode()
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })
    product_hint = f" (제품명: {product_name})" if product_name else ""
    content.append({
        "type": "text",
        "text": (
            f"위 영상 프레임들을 분석해 주세요{product_hint}.\n"
            "이 영상의 분위기, 편집 스타일, 타깃 고객층을 파악해서 "
            "이 제품을 홍보하는 15초 쇼츠 광고 컨셉 3가지를 제안해 주세요.\n"
            "반드시 JSON 배열만 반환하고 다른 텍스트는 포함하지 마세요."
        ),
    })
    return _call_claude(content)


def suggest_from_product(product_info: dict) -> list:
    """제품 정보만으로 쇼츠 광고 컨셉 3개를 반환 (영상 없을 때 폴백)."""
    name = product_info.get("name", "제품")
    price = product_info.get("price", "")
    desc = product_info.get("description", "")
    reviews = product_info.get("reviews", [])
    review_text = "\n".join(f"- {r}" for r in reviews[:3]) if reviews else "없음"

    text = (
        f"## 제품 정보\n"
        f"- 제품명: {name}\n"
        f"- 가격: {price}\n"
        f"- 설명: {desc}\n"
        f"- 리뷰:\n{review_text}\n\n"
        "위 제품을 홍보하는 광고티 없는 자연스러운 15초 쇼츠 광고 컨셉 3가지를 제안해 주세요.\n"
        "반드시 JSON 배열만 반환하고 다른 텍스트는 포함하지 마세요."
    )
    return _call_claude([{"type": "text", "text": text}])


def _call_claude(content: list) -> list:
    """Claude API 호출 → 컨셉 dict 리스트 반환."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    raw = resp.content[0].text.strip()
    # JSON 배열 추출 (```json ... ``` 래퍼 제거)
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Claude가 유효한 JSON을 반환하지 않았습니다:\n{raw[:300]}")
    return json.loads(match.group())
