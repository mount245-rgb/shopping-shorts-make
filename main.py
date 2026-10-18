"""쇼핑 쇼츠 자동화 CLI."""
import sys
import json
from pathlib import Path

import click
from tqdm import tqdm

import config
import topview_client as tv
import script_gen
import srt_builder
import ffmpeg_merge


@click.group()
def cli():
    """쇼핑 쇼츠 자동 제작 CLI"""


@cli.command()
@click.option("--link", "-l", required=True, help="쿠팡 또는 틱톡 제품 링크")
@click.option("--photos", "-p", multiple=True, help="사용 단계별 실사 사진 경로")
@click.option("--photo-desc", "-d", multiple=True, help="각 사진 설명 (--photos 순서와 동일)")
@click.option("--voice-id", default=None, help="Topview 음성 ID (미지정시 한국어 첫 번째)")
@click.option("--out", default=None, help="출력 디렉토리")
@click.option("--skip-video", is_flag=True, help="영상 생성 건너뜀")
def make(link, photos, photo_desc, voice_id, out, skip_video):
    """제품 링크 + 사용 사진으로 쇼츠 자동 제작."""
    from datetime import datetime

    out_dir = Path(out) if out else config.OUTPUT_DIR / f"shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"출력 디렉토리: {out_dir}")

    credit = tv.get_credit()
    click.echo(f"현재 크레딧: {credit:.1f}")

    # 1. 스크래핑
    click.echo("\n[1/6] 제품 정보 스크래핑 중...")
    from scraper import scrape_product, download_image
    product = scrape_product(link)
    click.echo(f"  제품명: {product['name']}")

    product_img_path = out_dir / "product_main.jpg"
    if product["image_urls"]:
        download_image(product["image_urls"][0], product_img_path)
    (out_dir / "product_info.json").write_text(
        json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 2. Topview 업로드
    click.echo("\n[2/6] 이미지 Topview 업로드...")
    product_file_id = tv.upload_file(product_img_path) if product_img_path.exists() else None
    if product_file_id:
        click.echo(f"  product fileId: {product_file_id}")

    photo_file_ids = []
    if photos:
        click.echo(f"  사용 사진 {len(photos)}장 업로드 중...")
        for i, photo in enumerate(tqdm(photos)):
            fid = tv.upload_file(photo)
            photo_file_ids.append(fid)
            click.echo(f"    사진{i+1} fileId: {fid}")

    # 3. 스크립트 생성
    click.echo("\n[3/6] AI 스크립트 생성 중...")
    descriptions = list(photo_desc) if photo_desc else [f"사용 단계 {i+1}" for i in range(len(photos))]
    cuts = script_gen.generate_script(product, usage_photos=descriptions or None)
    (out_dir / "script.json").write_text(json.dumps(cuts, ensure_ascii=False, indent=2), encoding="utf-8")
    for cut in cuts:
        click.echo(f"  Cut{cut['cut']}: [{cut['video_type']}] {cut.get('subtitle','')}")

    # 4. 영상 생성
    cut_paths = []
    if not skip_video:
        click.echo("\n[4/6] 영상 생성 중 (Topview)...")
        task_ids = []
        task_types = []

        for cut in cuts:
            vtype = cut.get("video_type", "omni_reference")
            prompt = cut.get("video_prompt", cut.get("narration", ""))
            duration = min(cut.get("seconds", 4), 8)

            if vtype == "image_to_video":
                pidx = cut.get("photo_index")
                fid = photo_file_ids[pidx] if (pidx is not None and pidx < len(photo_file_ids)) else (photo_file_ids[0] if photo_file_ids else product_file_id)
                tid = tv.generate_video_image_to_video(prompt, fid, duration=duration)
                task_types.append("image_to_video")
            else:
                if not product_file_id:
                    task_ids.append(None); task_types.append("omni_reference"); continue
                tid = tv.generate_video_omni_ref(prompt, product_file_id, duration=duration)
                task_types.append("omni_reference")

            click.echo(f"  Cut{cut['cut']} 제출: {tid}")
            task_ids.append(tid)

        click.echo("  완료 대기 중...")
        for tid, ttype, cut in zip(task_ids, task_types, cuts):
            if tid is None:
                cut_paths.append(None); continue
            url = tv.poll_task(tid, task_type=ttype)
            dest = out_dir / f"cut{cut['cut']}.mp4"
            tv.download_file(url, dest)
            cut_paths.append(dest)
            click.echo(f"  Cut{cut['cut']}: {dest.stat().st_size:,} bytes")
    else:
        click.echo("\n[4/6] 영상 생성 건너뜀")
        cut_paths = [out_dir / f"cut{i+1}.mp4" for i in range(len(cuts))]

    # 5. 나레이션
    click.echo("\n[5/6] 나레이션 생성 중...")
    narr_path = None
    if not voice_id:
        voices = tv.list_korean_voices()
        if voices:
            voice_id = voices[0]["voiceId"]
            click.echo(f"  음성: {voices[0].get('name', voice_id)}")

    if voice_id:
        full_narration = " ".join(c.get("narration", "") for c in cuts)
        narr_url = tv.generate_voice(voice_id, full_narration)
        narr_path = out_dir / "narration.mp3"
        tv.download_file(narr_url, narr_path)
        click.echo(f"  나레이션: {narr_path.stat().st_size:,} bytes")

    srt_path = out_dir / "subs.srt"
    srt_builder.build_srt(cuts, srt_path)
    click.echo(f"  자막: {srt_path}")

    # 6. FFmpeg 합성
    click.echo("\n[6/6] FFmpeg 합성 중...")
    valid = [(p, c) for p, c in zip(cut_paths, cuts) if p and Path(p).exists()]
    if not valid or not narr_path:
        click.echo("  합성 불가 (컷 또는 나레이션 없음)"); return

    output_mp4 = out_dir / "shorts_final.mp4"
    ffmpeg_merge.merge(
        [p for p, _ in valid],
        [c.get("seconds", 4) for _, c in valid],
        narr_path, srt_path, output_mp4,
    )
    click.echo(f"\n완료: {output_mp4} ({output_mp4.stat().st_size:,} bytes)")


@cli.command()
@click.argument("photos", nargs=-1, required=True)
@click.option("--out-dir", "-o", required=True)
@click.option("--cut", "cut_num", type=int, required=True)
@click.option("--duration", type=int, default=4)
@click.option("--prompt", default=None)
@click.option("--product-file-id", default=None)
def retry_cut(photos, out_dir, cut_num, duration, prompt, product_file_id):
    """특정 컷만 재생성."""
    out = Path(out_dir)
    if photos:
        fid = tv.upload_file(photos[0])
        p = prompt or "Close-up product repair, natural continuation, vertical 9:16"
        tid = tv.generate_video_image_to_video(p, fid, duration=duration)
        ttype = "image_to_video"
    elif product_file_id:
        p = prompt or "Product showcase, vertical 9:16"
        tid = tv.generate_video_omni_ref(p, product_file_id, duration=duration)
        ttype = "omni_reference"
    else:
        click.echo("--photos 또는 --product-file-id 필요"); sys.exit(1)

    click.echo(f"Cut{cut_num} 제출: {tid}")
    url = tv.poll_task(tid, task_type=ttype)
    dest = out / f"cut{cut_num}.mp4"
    tv.download_file(url, dest)
    click.echo(f"완료: {dest} ({dest.stat().st_size:,} bytes)")


@cli.command()
def credit():
    """현재 Topview 크레딧 확인."""
    c = tv.get_credit()
    click.echo(f"크레딧: {c:.1f}")


@cli.command()
@click.argument("cut_files", nargs=-1, required=True)
@click.option("--narration", "-n", required=True)
@click.option("--srt", "-s", required=True)
@click.option("--out", "-o", required=True)
@click.option("--durations", "-d", default="4,4,4,4,4,2")
def merge(cut_files, narration, srt, out, durations):
    """기존 컷들을 FFmpeg으로 합성."""
    dur_list = [int(x) for x in durations.split(",")]
    output = ffmpeg_merge.merge(
        [Path(p) for p in cut_files], dur_list,
        Path(narration), Path(srt), Path(out),
    )
    click.echo(f"완료: {output}")


if __name__ == "__main__":
    cli()
