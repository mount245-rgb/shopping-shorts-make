"""쇼핑 쇼츠 자동화 GUI — 4단계 위저드 (customtkinter)."""
import json
import os
import queue
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

import config
import topview_client as tv

try:
    import tkinterdnd2 as _dnd
    _HAS_DND = True
except ImportError:
    _HAS_DND = False

try:
    from PIL import ImageGrab as _ImageGrab
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

STAGE_LABELS = ["① 소재 입력", "② 컨셉 선택", "③ Cut1 검토", "④ 전체 제작"]
STYLE_COLORS = {
    "UGC리얼": "#27ae60",
    "감성비교": "#8e44ad",
    "언박싱": "#e67e22",
    "문제해결": "#2980b9",
}


class PhotoItem(ctk.CTkFrame):
    def __init__(self, master, path: str, desc: str, on_remove, **kw):
        super().__init__(master, **kw)
        self.path = path
        self.desc_var = ctk.StringVar(value=desc)
        ctk.CTkLabel(self, text=Path(path).name, width=170, anchor="w").pack(
            side="left", padx=(6, 4))
        ctk.CTkEntry(self, textvariable=self.desc_var, width=200,
                     placeholder_text="사진 설명").pack(side="left", padx=4)
        ctk.CTkButton(self, text="✕", width=28, fg_color="#c0392b",
                      command=lambda: on_remove(self)).pack(side="right", padx=4)


class ConceptCard(ctk.CTkFrame):
    def __init__(self, master, concept: dict, var: ctk.IntVar, idx: int, **kw):
        super().__init__(master, **kw)
        self.concept = concept
        style = concept.get("style", "")
        color = STYLE_COLORS.get(style, "#555555")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 2))
        ctk.CTkRadioButton(top, text="", variable=var, value=idx, width=24).pack(side="left")
        ctk.CTkLabel(top, text=concept.get("title", f"컨셉 {idx+1}"),
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(side="left", padx=4, fill="x", expand=True)
        ctk.CTkLabel(top, text=f" {style} ", fg_color=color, corner_radius=4,
                     font=ctk.CTkFont(size=11)).pack(side="right")

        ctk.CTkLabel(self, text=f'"{concept.get("hook", "")}"',
                     font=ctk.CTkFont(size=12, slant="italic"),
                     text_color="#aaaaaa", wraplength=540, anchor="w").pack(
            fill="x", padx=30, pady=(2, 0))
        ctk.CTkLabel(self, text=concept.get("description", ""),
                     font=ctk.CTkFont(size=11), text_color="#888888",
                     wraplength=540, anchor="w").pack(fill="x", padx=30, pady=(2, 8))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("쇼핑 쇼츠 메이커")
        self.geometry("760x900")
        self.resizable(True, True)

        self._q: queue.Queue = queue.Queue()
        self._photo_items: list = []
        self._concept_var = ctk.IntVar(value=0)
        self._s: dict = {}
        self._current_page = 0

        self._build_ui()
        if _HAS_DND:
            try:
                _dnd.TkinterDnD._require(self)
            except Exception:
                pass
        self._setup_dnd_and_paste()
        self._refresh_credit()
        self._poll_queue()

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, height=48)
        hdr.pack(fill="x", padx=12, pady=(12, 0))
        ctk.CTkLabel(hdr, text="🎬 쇼핑 쇼츠 메이커",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=12)
        self._credit_lbl = ctk.CTkLabel(hdr, text="크레딧: ...", font=ctk.CTkFont(size=13))
        self._credit_lbl.pack(side="right", padx=12)

        self._stage_bar = ctk.CTkFrame(self, height=40)
        self._stage_bar.pack(fill="x", padx=12, pady=(8, 0))
        self._stage_lbls = []
        for lbl in STAGE_LABELS:
            l = ctk.CTkLabel(self._stage_bar, text=lbl, font=ctk.CTkFont(size=12),
                             fg_color="#2b2b2b", corner_radius=6, padx=8, pady=4)
            l.pack(side="left", padx=4, pady=4)
            self._stage_lbls.append(l)

        self._pages_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._pages_frame.pack(fill="both", expand=True)

        self._pages = [
            self._build_page1(),
            self._build_page2(),
            self._build_page3(),
            self._build_page4(),
        ]
        self._show_page(0)

    def _build_page1(self) -> ctk.CTkScrollableFrame:
        page = ctk.CTkScrollableFrame(self._pages_frame)

        # Coupang link
        g = ctk.CTkFrame(page)
        g.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(g, text="제품 링크 (쿠팡 — 선택)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(6, 0))
        ctk.CTkLabel(
            g,
            text="⚠️ 쿠팡 / 쿠팡 파트너스 링크는 봇 차단으로 실패할 수 있습니다."
                 " 실패 시 아래 직접 입력을 사용하세요.",
            text_color="#e67e22", font=ctk.CTkFont(size=11),
            wraplength=680, anchor="w",
        ).pack(fill="x", padx=8)
        self._link_var = ctk.StringVar()
        ctk.CTkEntry(g, textvariable=self._link_var,
                     placeholder_text="https://www.coupang.com/...").pack(
            fill="x", padx=8, pady=(4, 8))

        # Manual product info
        g2 = ctk.CTkFrame(page)
        g2.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(g2, text="제품 정보 직접 입력 (링크 실패 시 필수)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(6, 0))
        for lbl, attr in [("제품명:", "_prod_name_var"), ("가격:", "_prod_price_var")]:
            row = ctk.CTkFrame(g2, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=lbl, width=60).pack(side="left")
            var = ctk.StringVar()
            setattr(self, attr, var)
            ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(g2, text="제품 설명:", anchor="w").pack(fill="x", padx=8, pady=(4, 0))
        self._prod_desc_txt = ctk.CTkTextbox(g2, height=72)
        self._prod_desc_txt.pack(fill="x", padx=8, pady=(2, 8))

        # Reference MP4
        g3 = ctk.CTkFrame(page)
        g3.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(g3, text="참고 영상 MP4 (선택 — 영상 분석으로 컨셉 제안)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(6, 0))
        row = ctk.CTkFrame(g3, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(2, 8))
        self._mp4_var = ctk.StringVar()
        self._mp4_entry = ctk.CTkEntry(row, textvariable=self._mp4_var,
                                       placeholder_text="없으면 제품 정보로 컨셉 제안")
        self._mp4_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="파일 선택", width=80,
                      command=self._pick_mp4).pack(side="right", padx=(6, 0))

        # Product image
        g4 = ctk.CTkFrame(page)
        g4.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(g4, text="제품 대표 이미지 (선택)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(6, 0))
        row = ctk.CTkFrame(g4, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(2, 8))
        self._prod_img_var = ctk.StringVar()
        self._prod_img_entry = ctk.CTkEntry(row, textvariable=self._prod_img_var,
                                            placeholder_text="제품 이미지 경로 (드래그 또는 Ctrl+V)")
        self._prod_img_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="파일 선택", width=80,
                      command=self._pick_prod_img).pack(side="right", padx=(6, 0))

        # Usage photos
        g5 = ctk.CTkFrame(page)
        g5.pack(fill="x", padx=12, pady=(10, 0))
        ph_hdr = ctk.CTkFrame(g5, fg_color="transparent")
        ph_hdr.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkLabel(ph_hdr, text="사용 단계 사진 (선택, 최대 6장)",
                     font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(ph_hdr, text="＋ 사진 추가", width=100,
                      command=self._add_photos).pack(side="right")
        ctk.CTkButton(ph_hdr, text="📋 붙여넣기", width=90, fg_color="#555555",
                      command=self._paste_photos).pack(side="right", padx=(0, 4))
        self._photo_frame = ctk.CTkScrollableFrame(g5, height=110)
        self._photo_frame.pack(fill="x", padx=8, pady=(4, 8))

        # Output folder
        g6 = ctk.CTkFrame(page)
        g6.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(g6, text="출력 폴더",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(6, 0))
        row = ctk.CTkFrame(g6, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(2, 8))
        self._out_var = ctk.StringVar(value=str(config.OUTPUT_DIR))
        ctk.CTkEntry(row, textvariable=self._out_var).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="폴더 선택", width=80,
                      command=self._pick_output).pack(side="right", padx=(6, 0))

        # Voice ID
        g7 = ctk.CTkFrame(page)
        g7.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(g7, text="음성 ID (비우면 자동 선택)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(6, 0))
        self._voice_var = ctk.StringVar()
        ctk.CTkEntry(g7, textvariable=self._voice_var,
                     placeholder_text="auto").pack(fill="x", padx=8, pady=(2, 8))

        self._analyze_btn = ctk.CTkButton(
            page, text="▶  컨셉 분석 시작", height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_analysis)
        self._analyze_btn.pack(fill="x", padx=12, pady=(14, 12))
        return page

    def _build_page2(self) -> ctk.CTkScrollableFrame:
        page = ctk.CTkScrollableFrame(self._pages_frame)
        ctk.CTkLabel(page, text="📋 광고 컨셉을 선택하세요",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=12, pady=(12, 6))
        self._concept_cards_frame = ctk.CTkFrame(page, fg_color="transparent")
        self._concept_cards_frame.pack(fill="x", padx=12, pady=4)
        self._pick_concept_btn = ctk.CTkButton(
            page, text="▶  이 컨셉으로 Cut 1 제작", height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_cut1)
        self._pick_concept_btn.pack(fill="x", padx=12, pady=(14, 4))
        ctk.CTkButton(page, text="← 소재 다시 입력", height=32, fg_color="#555555",
                      command=lambda: self._show_page(0)).pack(fill="x", padx=12, pady=(2, 12))
        return page

    def _build_page3(self) -> ctk.CTkScrollableFrame:
        page = ctk.CTkScrollableFrame(self._pages_frame)
        ctk.CTkLabel(page, text="🎬 Cut 1 검토",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=12, pady=(12, 4))

        self._cut1_progress = ctk.CTkProgressBar(page)
        self._cut1_progress.set(0)
        self._cut1_progress.pack(fill="x", padx=12, pady=(4, 0))
        self._cut1_status_lbl = ctk.CTkLabel(
            page, text="Cut 1 생성 중...", anchor="w", font=ctk.CTkFont(size=12))
        self._cut1_status_lbl.pack(fill="x", padx=12, pady=(2, 6))

        ctk.CTkLabel(page, text="Cut 1 스크립트",
                     font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x", padx=12, pady=(4, 0))
        self._cut1_script_txt = ctk.CTkTextbox(page, height=120, state="disabled")
        self._cut1_script_txt.pack(fill="x", padx=12, pady=(2, 4))

        self._cut1_path_lbl = ctk.CTkLabel(
            page, text="(아직 생성 전)", anchor="w",
            text_color="#888888", font=ctk.CTkFont(size=11))
        self._cut1_path_lbl.pack(fill="x", padx=12, pady=(0, 6))

        btn_row = ctk.CTkFrame(page, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=4)
        self._play_cut1_btn = ctk.CTkButton(
            btn_row, text="▶ Cut1 재생", fg_color="#27ae60", state="disabled",
            command=self._play_cut1)
        self._play_cut1_btn.pack(side="left", padx=(0, 6))
        self._retry_cut1_btn = ctk.CTkButton(
            btn_row, text="↩ 재생성", fg_color="#e67e22", state="disabled",
            command=self._retry_cut1)
        self._retry_cut1_btn.pack(side="left", padx=6)
        self._resume_cut1_btn = ctk.CTkButton(
            btn_row, text="⏱ 폴링 재시도", fg_color="#8e44ad", state="disabled",
            command=self._resume_cut1_poll)
        self._resume_cut1_btn.pack(side="left", padx=6)
        self._confirm_cut1_btn = ctk.CTkButton(
            btn_row, text="✅ 확인! 나머지 제작", state="disabled",
            command=self._start_remaining)
        self._confirm_cut1_btn.pack(side="right", padx=(6, 0))

        ctk.CTkLabel(page, text="로그", font=ctk.CTkFont(weight="bold"), anchor="w").pack(
            fill="x", padx=12, pady=(10, 0))
        self._log3 = ctk.CTkTextbox(
            page, height=200, font=ctk.CTkFont(family="Consolas", size=11))
        self._log3.pack(fill="both", expand=True, padx=12, pady=(2, 12))
        self._log3.configure(state="disabled")
        return page

    def _build_page4(self) -> ctk.CTkScrollableFrame:
        page = ctk.CTkScrollableFrame(self._pages_frame)
        ctk.CTkLabel(page, text="🚀 전체 영상 제작",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=12, pady=(12, 4))

        self._final_progress = ctk.CTkProgressBar(page)
        self._final_progress.set(0)
        self._final_progress.pack(fill="x", padx=12, pady=(4, 0))
        self._final_status_lbl = ctk.CTkLabel(
            page, text="제작 준비 중...", anchor="w", font=ctk.CTkFont(size=12))
        self._final_status_lbl.pack(fill="x", padx=12, pady=(2, 4))

        self._final_path_lbl = ctk.CTkLabel(
            page, text="", anchor="w", text_color="#27ae60", font=ctk.CTkFont(size=12))
        self._final_path_lbl.pack(fill="x", padx=12, pady=(0, 6))

        btn_row = ctk.CTkFrame(page, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=4)
        self._open_folder_btn = ctk.CTkButton(
            btn_row, text="📁 결과 폴더 열기", state="disabled", fg_color="#27ae60",
            command=self._open_result_folder)
        self._open_folder_btn.pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="🔄 새 영상 만들기",
                      command=self._reset).pack(side="right")

        ctk.CTkLabel(page, text="로그", font=ctk.CTkFont(weight="bold"), anchor="w").pack(
            fill="x", padx=12, pady=(10, 0))
        self._log4 = ctk.CTkTextbox(
            page, height=350, font=ctk.CTkFont(family="Consolas", size=11))
        self._log4.pack(fill="both", expand=True, padx=12, pady=(2, 12))
        self._log4.configure(state="disabled")
        return page

    # ── stage navigation ──────────────────────────────────────────

    def _show_page(self, idx: int):
        for p in self._pages:
            p.pack_forget()
        self._pages[idx].pack(fill="both", expand=True)
        for i, lbl in enumerate(self._stage_lbls):
            if i < idx:
                lbl.configure(fg_color="#27ae60", text_color="white")
            elif i == idx:
                lbl.configure(fg_color="#1f6aa5", text_color="white")
            else:
                lbl.configure(fg_color="#2b2b2b", text_color="#888888")
        self._current_page = idx

    # ── helpers ──────────────────────────────────────────────────

    def _refresh_credit(self):
        def _f():
            try:
                c = tv.get_credit()
                self._credit_lbl.configure(text=f"크레딧: {c:.1f}")
            except Exception:
                self._credit_lbl.configure(text="크레딧: 오류")
        threading.Thread(target=_f, daemon=True).start()

    def _pick_mp4(self):
        p = filedialog.askopenfilename(
            title="참고 영상 선택",
            filetypes=[("MP4", "*.mp4"), ("영상", "*.mp4 *.mov *.avi"), ("모든 파일", "*.*")])
        if p:
            self._mp4_var.set(p)

    def _pick_prod_img(self):
        p = filedialog.askopenfilename(
            title="제품 이미지 선택",
            filetypes=[("이미지", "*.jpg *.jpeg *.png *.webp"), ("모든 파일", "*.*")])
        if p:
            self._prod_img_var.set(p)

    def _add_photos(self):
        paths = filedialog.askopenfilenames(
            title="사진 선택",
            filetypes=[("이미지", "*.jpg *.jpeg *.png *.webp"), ("모든 파일", "*.*")])
        for p in paths:
            if len(self._photo_items) >= 6:
                messagebox.showwarning("제한", "사진은 최대 6장까지 추가할 수 있습니다.")
                break
            item = PhotoItem(self._photo_frame, p,
                             f"사용 단계 {len(self._photo_items)+1}",
                             on_remove=self._remove_photo)
            item.pack(fill="x", pady=2)
            self._photo_items.append(item)

    def _remove_photo(self, item):
        item.pack_forget()
        item.destroy()
        self._photo_items.remove(item)

    def _pick_output(self):
        d = filedialog.askdirectory(title="출력 폴더 선택")
        if d:
            self._out_var.set(d)

    # ── drag & drop / paste ───────────────────────────────────────

    def _setup_dnd_and_paste(self):
        if _HAS_DND:
            self._register_drop(self._mp4_entry, "_entry", self._on_mp4_drop)
            self._register_drop(self._prod_img_entry, "_entry", self._on_prod_img_drop)
            self._register_drop(self._photo_frame, "_parent_canvas", self._on_photos_drop)
        if _HAS_PIL:
            self._prod_img_entry.bind("<Control-v>", self._paste_prod_img)

    def _register_drop(self, widget, inner_attr, handler):
        target = getattr(widget, inner_attr, None) or widget
        try:
            target.drop_target_register(_dnd.DND_FILES)
            target.dnd_bind("<<Drop>>", handler)
            return
        except Exception:
            pass
        try:
            widget.drop_target_register(_dnd.DND_FILES)
            widget.dnd_bind("<<Drop>>", handler)
        except Exception:
            pass

    @staticmethod
    def _parse_dnd_data(data: str) -> list:
        """tkdnd event.data 에서 파일 경로 목록 추출 (공백 포함 경로 지원)."""
        result = []
        remaining = data.strip()
        while remaining:
            if remaining.startswith("{"):
                end = remaining.find("}")
                if end == -1:
                    result.append(remaining[1:])
                    break
                result.append(remaining[1:end])
                remaining = remaining[end + 1:].strip()
            else:
                parts = remaining.split(" ", 1)
                result.append(parts[0])
                remaining = parts[1].strip() if len(parts) > 1 else ""
        return result

    def _on_mp4_drop(self, event):
        paths = self._parse_dnd_data(event.data)
        mp4s = [p for p in paths if Path(p).suffix.lower() in (".mp4", ".mov", ".avi")]
        if mp4s:
            self._mp4_var.set(mp4s[0])

    def _on_prod_img_drop(self, event):
        paths = self._parse_dnd_data(event.data)
        imgs = [p for p in paths if Path(p).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        if imgs:
            self._prod_img_var.set(imgs[0])

    def _on_photos_drop(self, event):
        paths = self._parse_dnd_data(event.data)
        imgs = [p for p in paths if Path(p).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        self._add_photos_safe(imgs)

    def _add_photos_safe(self, imgs):
        for p in imgs:
            if len(self._photo_items) >= 6:
                messagebox.showwarning("제한", "사진은 최대 6장까지 추가할 수 있습니다.")
                break
            item = PhotoItem(self._photo_frame, p,
                             f"사용 단계 {len(self._photo_items)+1}",
                             on_remove=self._remove_photo)
            item.pack(fill="x", pady=2)
            self._photo_items.append(item)

    def _paste_prod_img(self, event=None):
        if not _HAS_PIL:
            return
        img = _ImageGrab.grabclipboard()
        if img is None:
            messagebox.showinfo("붙여넣기", "클립보드에 이미지가 없습니다.")
            return
        tmp = Path(tempfile.mktemp(suffix=".png"))
        img.save(tmp)
        self._prod_img_var.set(str(tmp))

    def _paste_photos(self):
        if not _HAS_PIL:
            messagebox.showinfo("알림", "Pillow 설치 필요: pip install Pillow")
            return
        img = _ImageGrab.grabclipboard()
        if img is None:
            messagebox.showinfo("붙여넣기", "클립보드에 이미지가 없습니다.")
            return
        if len(self._photo_items) >= 6:
            messagebox.showwarning("제한", "사진은 최대 6장까지 추가할 수 있습니다.")
            return
        tmp = Path(tempfile.mktemp(suffix=".png"))
        img.save(tmp)
        item = PhotoItem(self._photo_frame, str(tmp),
                         f"사용 단계 {len(self._photo_items)+1}",
                         on_remove=self._remove_photo)
        item.pack(fill="x", pady=2)
        self._photo_items.append(item)

    def _log_to(self, widget: ctk.CTkTextbox, text: str):
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _play_cut1(self):
        p = self._s.get("cut1_path")
        if p and Path(str(p)).exists():
            os.startfile(str(p))

    def _open_result_folder(self):
        d = self._s.get("out_dir")
        if d:
            os.startfile(str(d))

    def _reset(self):
        self._s = {}
        self._photo_items.clear()
        for w in self._photo_frame.winfo_children():
            w.destroy()
        for w in self._concept_cards_frame.winfo_children():
            w.destroy()
        self._concept_var.set(0)
        self._show_page(0)

    # ── Stage 1 → analysis ────────────────────────────────────────

    def _start_analysis(self):
        # Read all tkinter vars on main thread before spawning worker
        link = self._link_var.get().strip()
        prod_name = self._prod_name_var.get().strip()
        prod_price = self._prod_price_var.get().strip()
        prod_desc = self._prod_desc_txt.get("1.0", "end").strip()
        mp4_path = self._mp4_var.get().strip()
        prod_img = self._prod_img_var.get().strip()
        photos = [item.path for item in self._photo_items]
        descs = [item.desc_var.get() for item in self._photo_items]
        out_base = self._out_var.get().strip()
        voice_id = self._voice_var.get().strip() or None

        if not prod_name and not link:
            messagebox.showwarning("입력 오류", "제품 링크 또는 제품명을 입력하세요.")
            return

        self._analyze_btn.configure(state="disabled", text="분석 중...")
        self._s = {
            "photos": photos,
            "descs": descs,
            "voice_id": voice_id,
            "out_base": out_base,
        }
        threading.Thread(
            target=self._analysis_worker,
            args=(link, prod_name, prod_price, prod_desc,
                  mp4_path, prod_img, photos, descs, out_base),
            daemon=True,
        ).start()

    def _analysis_worker(self, link, prod_name, prod_price, prod_desc,
                         mp4_path, prod_img, photos, descs, out_base):
        try:
            import video_analyzer
            from scraper import scrape_product, download_image

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = Path(out_base) / f"shorts_{ts}"
            out_dir.mkdir(parents=True, exist_ok=True)
            self._s["out_dir"] = out_dir
            self._q.put(("log3", f"출력 폴더: {out_dir}"))

            # Build product dict
            product = {}
            if link:
                self._q.put(("log3", "제품 페이지 스크래핑 중..."))
                try:
                    product = scrape_product(link)
                    self._q.put(("log3", f"  성공: {product.get('name', '')}"))
                except Exception as e:
                    self._q.put(("log3", f"  실패 (수동 입력 사용): {e}"))

            if prod_name:
                product["name"] = prod_name
            if prod_price:
                product["price"] = prod_price
            if prod_desc:
                product["description"] = prod_desc
            product.setdefault("name", "제품")
            product.setdefault("price", "")
            product.setdefault("description", "")
            product.setdefault("reviews", [])
            product.setdefault("image_urls", [])
            self._s["product"] = product
            self._s["descs"] = descs
            self._q.put(("log3", f"제품명: {product['name']}"))

            # Product image
            product_img_path = None
            if prod_img and Path(prod_img).exists():
                product_img_path = Path(prod_img)
            elif product.get("image_urls"):
                p = out_dir / "product_main.jpg"
                self._q.put(("log3", "제품 이미지 다운로드 중..."))
                download_image(product["image_urls"][0], p)
                product_img_path = p
            self._s["product_img"] = product_img_path

            # Upload product image
            if product_img_path and product_img_path.exists():
                self._q.put(("log3", "제품 이미지 Topview 업로드 중..."))
                fid = tv.upload_file(product_img_path)
                self._s["product_file_id"] = fid
                self._q.put(("log3", f"  fileId: {fid}"))

            # Upload usage photos
            photo_file_ids = []
            for i, p in enumerate(photos):
                self._q.put(("log3", f"  사진{i+1} 업로드 중..."))
                fid = tv.upload_file(p)
                photo_file_ids.append(fid)
                self._q.put(("log3", f"  사진{i+1} fileId: {fid}"))
            self._s["photo_file_ids"] = photo_file_ids

            # Analyze / suggest concepts
            self._q.put(("log3", "컨셉 분석 중..."))
            if mp4_path and Path(mp4_path).exists():
                concepts = video_analyzer.analyze_video(mp4_path, product.get("name", ""))
                self._q.put(("log3", f"  영상 분석으로 컨셉 {len(concepts)}개 도출"))
            else:
                concepts = video_analyzer.suggest_from_product(product)
                self._q.put(("log3", f"  제품 정보로 컨셉 {len(concepts)}개 도출"))

            self._s["concepts"] = concepts
            self._q.put(("show_concepts", concepts))

        except Exception as e:
            import traceback
            self._q.put(("log3", f"\n오류: {e}\n{traceback.format_exc()}"))
            self._q.put(("analysis_error", str(e)))

    # ── Stage 2 → cut 1 generation ───────────────────────────────

    def _start_cut1(self):
        idx = self._concept_var.get()
        concepts = self._s.get("concepts", [])
        if not concepts:
            return
        concept = concepts[idx] if idx < len(concepts) else concepts[0]
        self._s["concept"] = concept
        self._show_page(2)
        self._cut1_status_lbl.configure(text="스크립트 생성 중...")
        self._cut1_progress.set(0.05)
        self._play_cut1_btn.configure(state="disabled")
        self._retry_cut1_btn.configure(state="disabled")
        self._confirm_cut1_btn.configure(state="disabled")
        self._generate_cut1()

    def _generate_cut1(self):
        product = self._s.get("product", {})
        descs = self._s.get("descs", [])
        concept = self._s.get("concept")
        threading.Thread(
            target=self._cut1_worker,
            args=(product, descs, concept),
            daemon=True,
        ).start()

    def _cut1_worker(self, product, descs, concept):
        try:
            import script_gen
            if "cuts" not in self._s:
                self._q.put(("log3", "\nAI 스크립트 생성 중..."))
                cuts = script_gen.generate_script(
                    product, usage_photos=descs or None, concept=concept)
                self._s["cuts"] = cuts
                out_dir = self._s.get("out_dir")
                if out_dir:
                    (out_dir / "script.json").write_text(
                        json.dumps(cuts, ensure_ascii=False, indent=2), encoding="utf-8")
                for c in cuts:
                    self._q.put(("log3", f"  Cut{c['cut']}: {c.get('subtitle', '')}"))
            else:
                cuts = self._s["cuts"]

            cut1 = cuts[0]
            script_txt = (
                f"[비디오 프롬프트]\n{cut1.get('video_prompt', '')}\n\n"
                f"[자막] {cut1.get('subtitle', '')}\n"
                f"[나레이션] {cut1.get('narration', '')}\n"
                f"[타입] {cut1.get('video_type', '')} | {cut1.get('seconds', 4)}초"
            )
            self._q.put(("cut1_script", script_txt))
            self._q.put(("cut1_progress", 0.3))
            self._q.put(("log3", "Cut 1 영상 생성 요청 중..."))

            product_file_id = self._s.get("product_file_id")
            photo_file_ids = self._s.get("photo_file_ids", [])
            prompt = cut1.get("video_prompt", cut1.get("narration", ""))
            duration = min(cut1.get("seconds", 4), 8)
            vtype = cut1.get("video_type", "omni_reference")

            if vtype == "image_to_video":
                pidx = cut1.get("photo_index")
                fid = (photo_file_ids[pidx]
                       if pidx is not None and pidx < len(photo_file_ids)
                       else (photo_file_ids[0] if photo_file_ids else product_file_id))
                if not fid:
                    raise ValueError("image_to_video에 사용할 이미지 fileId가 없습니다.")
                tid = tv.generate_video_image_to_video(prompt, fid, duration=duration)
            else:
                if not product_file_id:
                    raise ValueError(
                        "제품 이미지 fileId가 없습니다. 1단계에서 제품 이미지를 추가하세요.")
                tid = tv.generate_video_omni_ref(prompt, product_file_id, duration=duration)

            self._q.put(("log3", f"  Cut1 taskId: {tid}"))
            self._s["cut1_task_id"] = tid
            self._s["cut1_vtype"] = vtype
            self._q.put(("cut1_progress", 0.5))
            self._q.put(("log3", "  완료 대기 중 (최대 15분)..."))

            url = tv.poll_task(tid, task_type=vtype)
            out_dir = Path(self._s["out_dir"])
            dest = out_dir / "cut1.mp4"
            tv.download_file(url, dest)
            self._s["cut1_path"] = dest
            self._q.put(("log3", f"  Cut1 완료: {dest} ({dest.stat().st_size:,} bytes)"))
            self._q.put(("cut1_done", str(dest)))

        except TimeoutError as e:
            self._q.put(("log3",
                "\nCut1 타임아웃! Topview에서 영상이 계속 생성 중일 수 있습니다.\n"
                "'폴링 재시도' 버튼으로 기다리세요. (크레딧 추가 차감 없음)"))
            self._q.put(("cut1_timeout", str(e)))
        except Exception as e:
            import traceback
            self._q.put(("log3", f"\nCut1 오류: {e}\n{traceback.format_exc()}"))
            self._q.put(("cut1_error", str(e)))

    def _retry_cut1(self):
        self._s.pop("cut1_path", None)
        self._s.pop("cut1_task_id", None)
        self._play_cut1_btn.configure(state="disabled")
        self._retry_cut1_btn.configure(state="disabled")
        self._resume_cut1_btn.configure(state="disabled")
        self._confirm_cut1_btn.configure(state="disabled")
        self._cut1_status_lbl.configure(text="Cut 1 재생성 중...")
        self._cut1_progress.set(0.05)
        self._generate_cut1()

    def _resume_cut1_poll(self):
        tid = self._s.get("cut1_task_id")
        vtype = self._s.get("cut1_vtype", "omni_reference")
        if not tid:
            messagebox.showerror("오류", "재시도할 taskId가 없습니다.")
            return
        self._resume_cut1_btn.configure(state="disabled")
        self._retry_cut1_btn.configure(state="disabled")
        self._cut1_status_lbl.configure(text="폴링 재시도 중... (최대 15분)")
        self._cut1_progress.set(0.5)
        self._log_to(self._log3, f"  폴링 재시도: taskId={tid}")

        def _resume_worker():
            try:
                url = tv.poll_task(tid, task_type=vtype)
                out_dir = Path(self._s["out_dir"])
                dest = out_dir / "cut1.mp4"
                tv.download_file(url, dest)
                self._s["cut1_path"] = dest
                self._q.put(("log3", f"  Cut1 완료: {dest} ({dest.stat().st_size:,} bytes)"))
                self._q.put(("cut1_done", str(dest)))
            except TimeoutError as e:
                self._q.put(("log3", f"\nCut1 타임아웃: {e}"))
                self._q.put(("cut1_timeout", str(e)))
            except Exception as e:
                import traceback
                self._q.put(("log3", f"\nCut1 오류: {e}\n{traceback.format_exc()}"))
                self._q.put(("cut1_error", str(e)))

        threading.Thread(target=_resume_worker, daemon=True).start()

    # ── Stage 3 → remaining cuts ──────────────────────────────────

    def _start_remaining(self):
        self._show_page(3)
        self._final_status_lbl.configure(text="나머지 컷 생성 중...")
        self._final_progress.set(0.05)
        self._open_folder_btn.configure(state="disabled")

        cuts = self._s.get("cuts", [])
        product_file_id = self._s.get("product_file_id")
        photo_file_ids = self._s.get("photo_file_ids", [])
        voice_id = self._s.get("voice_id")
        out_dir = self._s.get("out_dir")
        cut1_path = self._s.get("cut1_path")

        threading.Thread(
            target=self._remaining_worker,
            args=(cuts, product_file_id, photo_file_ids, voice_id, out_dir, cut1_path),
            daemon=True,
        ).start()

    def _remaining_worker(self, cuts, product_file_id, photo_file_ids,
                          voice_id, out_dir, cut1_path):
        try:
            import srt_builder, ffmpeg_merge
            out_dir = Path(out_dir)

            self._q.put(("log4", "Cut 2~6 영상 생성 요청 중 (병렬)..."))
            task_ids, task_types = [], []
            remaining = cuts[1:] if len(cuts) > 1 else []

            for cut in remaining:
                prompt = cut.get("video_prompt", cut.get("narration", ""))
                duration = min(cut.get("seconds", 4), 8)
                vtype = cut.get("video_type", "omni_reference")
                tid = None
                if vtype == "image_to_video":
                    pidx = cut.get("photo_index")
                    fid = (photo_file_ids[pidx]
                           if pidx is not None and pidx < len(photo_file_ids)
                           else (photo_file_ids[0] if photo_file_ids else product_file_id))
                    if fid:
                        tid = tv.generate_video_image_to_video(prompt, fid, duration=duration)
                else:
                    if product_file_id:
                        tid = tv.generate_video_omni_ref(prompt, product_file_id, duration=duration)
                task_ids.append(tid)
                task_types.append(vtype)
                self._q.put(("log4", f"  Cut{cut['cut']} 제출: {tid or '건너뜀'}"))

            self._q.put(("log4", "  완료 대기 중..."))
            self._q.put(("final_progress", 0.15))

            cut_paths = [cut1_path] if cut1_path and Path(str(cut1_path)).exists() else [None]
            total = max(len(remaining), 1)
            for i, (tid, ttype, cut) in enumerate(zip(task_ids, task_types, remaining)):
                if tid is None:
                    cut_paths.append(None)
                    continue
                url = tv.poll_task(tid, task_type=ttype)
                dest = out_dir / f"cut{cut['cut']}.mp4"
                tv.download_file(url, dest)
                cut_paths.append(dest)
                self._q.put(("log4", f"  Cut{cut['cut']}: {dest.stat().st_size:,} bytes"))
                self._q.put(("final_progress", 0.15 + 0.45 * (i + 1) / total))

            # Voice
            self._q.put(("log4", "\n나레이션 생성 중..."))
            self._q.put(("final_status", "나레이션 생성 중..."))
            narr_path = None
            v_id = voice_id
            if not v_id:
                voices = tv.list_korean_voices()
                if voices:
                    first = voices[0]
                    v_id = (first.get("voiceId") or first.get("id")
                            or first.get("voice_id") or "")
                    if v_id:
                        self._q.put(("log4", f"  음성 자동선택: {first.get('name', v_id)}"))
                    else:
                        self._q.put(("log4", f"  음성 키 파싱 실패. 응답: {first}"))
            if v_id:
                try:
                    full_narration = " ".join(
                        c.get("narration", "") for c in cuts if c.get("narration", "").strip()
                    )
                    if not full_narration.strip():
                        self._q.put(("log4", "  나레이션 텍스트 없음 — 건너뜀"))
                    else:
                        self._q.put(("log4", f"  나레이션 텍스트 {len(full_narration)}자 전송 중..."))
                        narr_url = tv.generate_voice(v_id, full_narration)
                        narr_path = out_dir / "narration.mp3"
                        tv.download_file(narr_url, narr_path)
                        self._q.put(("log4", f"  나레이션 완료: {narr_path.stat().st_size:,} bytes"))
                except Exception as ve:
                    self._q.put(("log4", f"  나레이션 생성 실패 (자막만 합성): {ve}"))
                    narr_path = None
            else:
                self._q.put(("log4", "  음성 ID 없음 — 나레이션 생략"))

            srt_path = out_dir / "subs.srt"
            srt_builder.build_srt(cuts, srt_path)
            srt_size = srt_path.stat().st_size
            self._q.put(("log4", f"  자막 파일: {srt_path} ({srt_size} bytes)"))
            self._q.put(("final_progress", 0.75))

            # Merge
            self._q.put(("log4", "\nFFmpeg 합성 중..."))
            self._q.put(("final_status", "FFmpeg 합성 중..."))
            valid = [(p, c) for p, c in zip(cut_paths, cuts)
                     if p and Path(str(p)).exists()]
            if not valid:
                self._q.put(("log4", "  합성 불가 (유효한 컷 없음)"))
                self._q.put(("final_done", str(out_dir)))
                return

            output_mp4 = out_dir / "shorts_final.mp4"
            ffmpeg_merge.merge(
                [p for p, _ in valid],
                [c.get("seconds", 4) for _, c in valid],
                narr_path, srt_path, output_mp4,
            )
            sz = output_mp4.stat().st_size
            self._q.put(("log4", f"\n완료: {output_mp4} ({sz:,} bytes)"))
            self._q.put(("final_progress", 1.0))
            self._q.put(("final_done", str(output_mp4)))
            self._refresh_credit()

        except Exception as e:
            import traceback
            self._q.put(("log4", f"\n오류: {e}\n{traceback.format_exc()}"))
            self._q.put(("final_error", str(e)))

    # ── queue processor ───────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg = self._q.get_nowait()
                cmd = msg[0]

                if cmd == "log3":
                    self._log_to(self._log3, msg[1])
                elif cmd == "log4":
                    self._log_to(self._log4, msg[1])

                elif cmd == "show_concepts":
                    concepts = msg[1]
                    for w in self._concept_cards_frame.winfo_children():
                        w.destroy()
                    self._concept_var.set(0)
                    for i, c in enumerate(concepts):
                        card = ConceptCard(
                            self._concept_cards_frame, c,
                            self._concept_var, i,
                            fg_color="#2b2b2b", corner_radius=8)
                        card.pack(fill="x", pady=6)
                    self._analyze_btn.configure(
                        state="normal", text="▶  컨셉 분석 시작")
                    self._show_page(1)

                elif cmd == "analysis_error":
                    self._analyze_btn.configure(
                        state="normal", text="▶  컨셉 분석 시작")
                    messagebox.showerror("분석 오류", msg[1])

                elif cmd == "cut1_script":
                    self._cut1_script_txt.configure(state="normal")
                    self._cut1_script_txt.delete("1.0", "end")
                    self._cut1_script_txt.insert("1.0", msg[1])
                    self._cut1_script_txt.configure(state="disabled")

                elif cmd == "cut1_progress":
                    self._cut1_progress.set(msg[1])

                elif cmd == "cut1_done":
                    self._cut1_progress.set(1.0)
                    self._cut1_status_lbl.configure(text="✅ Cut 1 완료!")
                    self._cut1_path_lbl.configure(
                        text=msg[1], text_color="#27ae60")
                    self._play_cut1_btn.configure(state="normal")
                    self._retry_cut1_btn.configure(state="normal")
                    self._confirm_cut1_btn.configure(state="normal")

                elif cmd == "cut1_error":
                    self._cut1_progress.set(0)
                    self._cut1_status_lbl.configure(text="오류 발생")
                    self._retry_cut1_btn.configure(state="normal")
                    messagebox.showerror("Cut1 오류", msg[1])

                elif cmd == "cut1_timeout":
                    self._cut1_progress.set(0)
                    self._cut1_status_lbl.configure(text="⏱ 타임아웃 — 재시도 가능")
                    self._retry_cut1_btn.configure(state="normal")
                    self._resume_cut1_btn.configure(state="normal")
                    messagebox.showwarning(
                        "Cut1 타임아웃",
                        "15분을 초과했습니다.\n"
                        "Topview에서 영상이 계속 생성 중일 수 있습니다.\n\n"
                        "◆ '⏱ 폴링 재시도' — 기존 작업 결과 대기 (크레딧 추가 차감 없음)\n"
                        "◆ '↩ 재생성' — 새 영상 생성 (크레딧 차감)")

                elif cmd == "final_progress":
                    self._final_progress.set(msg[1])

                elif cmd == "final_status":
                    self._final_status_lbl.configure(text=msg[1])

                elif cmd == "final_done":
                    self._final_progress.set(1.0)
                    self._final_status_lbl.configure(text="✅ 제작 완료!")
                    self._final_path_lbl.configure(text=msg[1])
                    self._open_folder_btn.configure(state="normal")

                elif cmd == "final_error":
                    self._final_progress.set(0)
                    self._final_status_lbl.configure(text="오류 발생")
                    messagebox.showerror("제작 오류", msg[1])

        except queue.Empty:
            pass
        self.after(100, self._poll_queue)


if __name__ == "__main__":
    app = App()
    app.mainloop()
