"""FFmpeg 파이프라인 -- 6컷 + 나레이션 + 자막 합성."""
import subprocess
from pathlib import Path

import config


def merge(
    cut_files: list,
    durations: list,
    narration_path,  # Path | None
    srt_path: Path,
    output_path: Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    srt_escaped = str(srt_path).replace("\\", "/").replace(":/", "\\:/")

    filter_parts = []
    for i, (path, d) in enumerate(zip(cut_files, durations)):
        filter_parts.append(
            f"[{i}:v]scale=720:1280:force_original_aspect_ratio=decrease,"
            f"pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"trim=duration={d},setpts=PTS-STARTPTS[v{i}];"
        )

    concat_in = "".join(f"[v{i}]" for i in range(len(cut_files)))
    filter_parts.append(f"{concat_in}concat=n={len(cut_files)}:v=1:a=0[vcat];")
    filter_parts.append(
        f"[vcat]subtitles='{srt_escaped}':"
        f"force_style='FontName=Malgun Gothic Bold,FontSize=22,"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        f"Outline=2,Shadow=1,Alignment=2,MarginV=60'[vout]"
    )
    filter_complex = "".join(filter_parts)

    input_args = []
    for p in cut_files:
        input_args += ["-i", str(p)]

    has_narration = narration_path and Path(str(narration_path)).exists()

    if has_narration:
        cmd = (
            [config.FFMPEG_PATH]
            + input_args
            + ["-i", str(narration_path)]
            + ["-filter_complex", filter_complex]
            + ["-map", "[vout]"]
            + ["-map", f"{len(cut_files)}:a"]
            + ["-c:v", "libx264", "-crf", "23", "-preset", "fast"]
            + ["-c:a", "aac", "-b:a", "192k"]
            + ["-shortest", "-y", str(output_path)]
        )
    else:
        # 나레이션 없이 영상 + 자막만 합성
        cmd = (
            [config.FFMPEG_PATH]
            + input_args
            + ["-filter_complex", filter_complex]
            + ["-map", "[vout]"]
            + ["-c:v", "libx264", "-crf", "23", "-preset", "fast"]
            + ["-an", "-y", str(output_path)]
        )

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 실패:\n{result.stderr[-2000:]}")

    return output_path
