"""SRT 자막 파일 생성 (UTF-8 without BOM)."""
from pathlib import Path


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(cuts: list, output_path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    current_time = 0.0

    for i, cut in enumerate(cuts, start=1):
        start = current_time
        end = current_time + cut.get("seconds", 4)
        subtitle = cut.get("subtitle", "").strip()
        if subtitle:
            lines.append(str(i))
            lines.append(f"{_fmt_time(start)} --> {_fmt_time(end)}")
            lines.append(subtitle)
            lines.append("")
        current_time = end

    content = "\n".join(lines)
    # UTF-8 without BOM
    output_path.write_text(content, encoding="utf-8")
    return output_path
