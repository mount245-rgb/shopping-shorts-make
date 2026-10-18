"""Anthropic API로 6컷 쇼츠 스크립트 자동 생성."""
import json
import re

import anthropic
import config

_CLIENT = None

def _client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _CLIENT


SYSTEM_PROMPT = """당신은 쿠팡/틱톡 파트너스 쇼핑 쇼츠 전문 카피라이터입니다.
15초 6컷 구조로 자연스럽고 광고티 없는 스크립트를 작성합니다.
반드시 JSON 형식으로만 응답하세요."""

CUT_STRUCTURE = [
    {"cut": 1, "seconds": 4, "role": "Hook -- 강렬한 첫 장면, 시청자 이탈 방지"},
    {"cut": 2, "seconds": 4, "role": "문제 제기 -- 공감되는 불편함 연출"},
    {"cut": 3, "seconds": 4, "role": "제품 등장 -- 임팩트 있는 리빌"},
    {"cut": 4, "seconds": 4, "role": "해결 과정 -- 제품 사용 장면"},
    {"cut": 5, "seconds": 4, "role": "사용 전후 비교 -- 극적 변화"},
    {"cut": 6, "seconds": 2, "role": "CTA -- 링크 클릭 유도"},
]


def generate_script(product_info: dict, usage_photos: list = None, concept: dict = None) -> list:
    """
    반환: [{cut, seconds, role, video_prompt, subtitle, narration,
             video_type, photo_index}, ...]
    """
    photo_desc = ""
    if usage_photos:
        lines = "\n".join(f"- 사진{i+1}: {desc}" for i, desc in enumerate(usage_photos))
        photo_desc = f"\n\n## 실제 사용 단계 사진 (firstFrame으로 사용)\n{lines}"

    concept_desc = ""
    if concept:
        concept_desc = (
            f"\n\n## 선택된 광고 컨셉 (반드시 이 방향으로 작성)\n"
            f"- 제목: {concept.get('title', '')}\n"
            f"- 스타일: {concept.get('style', '')}\n"
            f"- 초반 후킹 문구: {concept.get('hook', '')}\n"
            f"- 나레이션 톤: {concept.get('narration_tone', '')}\n"
            f"- 설명: {concept.get('description', '')}"
        )

    user_msg = f"""## 제품 정보
이름: {product_info.get('name', '알 수 없음')}
가격: {product_info.get('price', '')}
설명: {product_info.get('description', '')[:300]}
리뷰: {chr(10).join(product_info.get('reviews', [])[:3])}{photo_desc}{concept_desc}

## 6컷 구조 (총 15초)
{json.dumps(CUT_STRUCTURE, ensure_ascii=False, indent=2)}

## 요청
위 제품으로 15초 쇼핑 쇼츠 스크립트를 작성하세요.
각 컷마다:
- video_prompt: 영어, Topview AI 영상 생성용, 9:16 vertical, wan3.0 모델
- subtitle: 한국어 자막 (화면 표시용, 간결하게)
- narration: 한국어 나레이션 대본
- video_type: 사용 사진이 있는 컷은 "image_to_video", 나머지는 "omni_reference"
- photo_index: image_to_video인 컷에만 usage_photos 배열 인덱스(0부터), 없으면 null

JSON 배열로만 응답하세요."""

    resp = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": user_msg}],
        system=SYSTEM_PROMPT,
    )
    raw = resp.content[0].text.strip()

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"스크립트 JSON 파싱 실패:\n{raw}")
    cuts = json.loads(match.group())

    for i, cut in enumerate(cuts):
        cut.setdefault("video_type", "omni_reference")
        cut.setdefault("photo_index", None)
        if not cut.get("seconds"):
            cut["seconds"] = CUT_STRUCTURE[i]["seconds"] if i < len(CUT_STRUCTURE) else 4

    return cuts
