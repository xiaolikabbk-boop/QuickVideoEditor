from __future__ import annotations

import json
import os
import queue
import threading
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkinterdnd2 import DND_FILES
from tkinterdnd2.TkinterDnD import DnDWrapper, _require

from music_batcher import (
    VIDEO_EXTENSIONS,
    ExportJob,
    MediaError,
    assign_music,
    assign_overlays,
    export_job,
    find_images,
    find_music,
    output_path_for,
)
from update_service import (
    PreparedUpdate,
    ReleaseInfo,
    UpdateError,
    fetch_latest_release,
    install_prepared_update,
    prepare_update,
)
from version import APP_NAME, APP_VERSION


CONFIG_PATH = Path(os.getenv("APPDATA", Path.home())) / "QuickMusicBatch" / "config.json"


class CTkDnD(ctk.CTk, DnDWrapper):
    def __init__(self, *args, **kwargs):
        ctk.CTk.__init__(self, *args, **kwargs)
        DnDWrapper.__init__(self)
        self.TkdndVersion = _require(self)


class App(CTkDnD):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("980x760")
        self.minsize(820, 680)
        self.configure(fg_color="#f4f5f7")
        ctk.set_appearance_mode("light")

        self.videos: list[Path] = []
        self.music_folder = ctk.StringVar(value=self._load_music_folder())
        self.image_folder = ctk.StringVar(value=self._load_config().get("image_folder", ""))
        self.use_images = ctk.BooleanVar(value=False)
        self.use_outline = ctk.BooleanVar(value=False)
        self.source_volume = ctk.DoubleVar(value=70)
        self.music_volume = ctk.DoubleVar(value=25)
        self.events: queue.Queue[tuple] = queue.Queue()
        self.running = False
        self.checking_update = False
        self.update_dialog = None
        self.update_action_button = None

        self._build_ui()
        self.after(100, self._drain_events)
        self.after(1500, lambda: self._check_updates(manual=False))

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#ffffff", corner_radius=0, height=74)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text=APP_NAME, font=("Microsoft YaHei UI", 22, "bold"), text_color="#17202a").pack(side="left", padx=28)
        self.summary_label = ctk.CTkLabel(header, text="0 条视频", font=("Microsoft YaHei UI", 13), text_color="#68707a")
        self.summary_label.pack(side="right", padx=28)
        self.update_button = ctk.CTkButton(
            header,
            text="检查更新",
            command=lambda: self._check_updates(manual=True),
            width=86,
            height=32,
            fg_color="transparent",
            hover_color="#eef0f2",
            text_color="#35404a",
            border_width=1,
            border_color="#cbd1d8",
        )
        self.update_button.pack(side="right")
        ctk.CTkLabel(
            header,
            text=f"v{APP_VERSION}",
            font=("Microsoft YaHei UI", 12),
            text_color="#68707a",
        ).pack(side="right", padx=(0, 12))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="#ffffff", corner_radius=8, border_width=1, border_color="#dfe3e8")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="待处理视频", font=("Microsoft YaHei UI", 16, "bold"), text_color="#17202a").grid(row=0, column=0, sticky="w", padx=20, pady=(18, 10))

        drop = ctk.CTkFrame(left, fg_color="#edf7f2", corner_radius=6, border_width=1, border_color="#74b998", height=90)
        drop.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 12))
        drop.grid_propagate(False)
        drop_label = ctk.CTkLabel(drop, text="拖入视频到这里\n也可以点击下方按钮选择", font=("Microsoft YaHei UI", 14), text_color="#276749")
        drop_label.place(relx=0.5, rely=0.5, anchor="center")
        for widget in (drop, drop_label):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)

        self.video_list = ctk.CTkScrollableFrame(left, fg_color="#ffffff", corner_radius=0)
        self.video_list.grid(row=2, column=0, sticky="nsew", padx=12)

        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=20, pady=16)
        ctk.CTkButton(actions, text="添加视频", command=self._choose_videos, width=110, fg_color="#237a57", hover_color="#1d684a").pack(side="left")
        ctk.CTkButton(actions, text="清空", command=self._clear_videos, width=76, fg_color="transparent", hover_color="#eef0f2", text_color="#4d5660", border_width=1, border_color="#cbd1d8").pack(side="left", padx=8)

        right = ctk.CTkFrame(body, fg_color="#ffffff", corner_radius=8, border_width=1, border_color="#dfe3e8")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right, text="配乐设置", font=("Microsoft YaHei UI", 16, "bold"), text_color="#17202a").grid(row=0, column=0, sticky="w", padx=20, pady=(18, 14))

        ctk.CTkLabel(right, text="音乐文件夹", font=("Microsoft YaHei UI", 13, "bold"), text_color="#35404a").grid(row=1, column=0, sticky="w", padx=20)
        folder_row = ctk.CTkFrame(right, fg_color="transparent")
        folder_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(7, 18))
        folder_row.grid_columnconfigure(0, weight=1)
        self.folder_entry = ctk.CTkEntry(folder_row, textvariable=self.music_folder, height=36, state="readonly")
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(folder_row, text="选择", command=self._choose_music_folder, width=62, height=36, fg_color="#4d5966", hover_color="#3d4751").grid(row=0, column=1)

        image_switch = ctk.CTkSwitch(
            right,
            text="叠加透明图片（可选）",
            variable=self.use_images,
            command=self._toggle_image_controls,
            font=("Microsoft YaHei UI", 13, "bold"),
            text_color="#35404a",
            progress_color="#237a57",
        )
        image_switch.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 7))
        image_row = ctk.CTkFrame(right, fg_color="transparent")
        image_row.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 18))
        image_row.grid_columnconfigure(0, weight=1)
        self.image_entry = ctk.CTkEntry(image_row, textvariable=self.image_folder, height=36, state="disabled")
        self.image_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.image_button = ctk.CTkButton(image_row, text="选择", command=self._choose_image_folder, width=62, height=36, state="disabled", fg_color="#4d5966", hover_color="#3d4751")
        self.image_button.grid(row=0, column=1)

        self.outline_switch = ctk.CTkSwitch(
            right,
            text="添加白色描边",
            variable=self.use_outline,
            state="disabled",
            font=("Microsoft YaHei UI", 13),
            text_color="#35404a",
            progress_color="#237a57",
        )
        self.outline_switch.grid(row=5, column=0, sticky="w", padx=20, pady=(0, 16))

        self.source_value = self._add_slider(right, 6, "原视频声音", self.source_volume)
        self.music_value = self._add_slider(right, 8, "背景音乐", self.music_volume)

        rules = ctk.CTkFrame(right, fg_color="#f7f8fa", corner_radius=6)
        rules.grid(row=10, column=0, sticky="ew", padx=20, pady=(8, 8))
        ctk.CTkLabel(
            rules,
            text="音乐/图片优先不重复  ·  短歌自动循环\n透明图贴底居中  ·  音乐结尾 1 秒淡出",
            justify="left", font=("Microsoft YaHei UI", 12), text_color="#59636e",
        ).pack(anchor="w", padx=14, pady=12)

        self.progress = ctk.CTkProgressBar(right, height=10, progress_color="#237a57")
        self.progress.grid(row=11, column=0, sticky="ew", padx=20, pady=(12, 8))
        self.progress.set(0)
        self.status_label = ctk.CTkLabel(right, text="准备就绪", anchor="w", font=("Microsoft YaHei UI", 12), text_color="#68707a")
        self.status_label.grid(row=12, column=0, sticky="ew", padx=20)
        self.export_button = ctk.CTkButton(right, text="开始批量导出", command=self._start_export, height=44, font=("Microsoft YaHei UI", 14, "bold"), fg_color="#237a57", hover_color="#1d684a")
        self.export_button.grid(row=13, column=0, sticky="ew", padx=20, pady=20)

    def _add_slider(self, parent, row, label, variable):
        line = ctk.CTkFrame(parent, fg_color="transparent")
        line.grid(row=row, column=0, sticky="ew", padx=20)
        ctk.CTkLabel(line, text=label, font=("Microsoft YaHei UI", 13, "bold"), text_color="#35404a").pack(side="left")
        value_label = ctk.CTkLabel(line, text=f"{int(variable.get())}%", font=("Microsoft YaHei UI", 12), text_color="#237a57", width=42)
        value_label.pack(side="right")
        slider = ctk.CTkSlider(parent, from_=0, to=100, variable=variable, command=lambda value: value_label.configure(text=f"{int(value)}%"), progress_color="#237a57", button_color="#237a57", button_hover_color="#1d684a")
        slider.grid(row=row + 1, column=0, sticky="ew", padx=20, pady=(7, 15))
        return value_label

    def _on_drop(self, event):
        self._add_videos(Path(value) for value in self.tk.splitlist(event.data))

    def _choose_videos(self):
        paths = filedialog.askopenfilenames(title="选择视频", filetypes=[("视频文件", "*.mp4 *.mov *.mkv *.avi *.m4v *.webm"), ("所有文件", "*.*")])
        self._add_videos(Path(path) for path in paths)

    def _add_videos(self, paths):
        existing = {path.resolve() for path in self.videos}
        for path in paths:
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS and path.resolve() not in existing:
                self.videos.append(path.resolve())
                existing.add(path.resolve())
        self._render_videos()

    def _render_videos(self):
        for child in self.video_list.winfo_children():
            child.destroy()
        for index, path in enumerate(self.videos):
            row = ctk.CTkFrame(self.video_list, fg_color="#f7f8fa", corner_radius=5, height=48)
            row.pack(fill="x", pady=3)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=path.name, anchor="w", font=("Microsoft YaHei UI", 12), text_color="#303942").pack(side="left", fill="x", expand=True, padx=12)
            ctk.CTkButton(row, text="×", width=32, height=28, fg_color="transparent", hover_color="#f1dddd", text_color="#8b3f3f", command=lambda i=index: self._remove_video(i)).pack(side="right", padx=7)
        self.summary_label.configure(text=f"{len(self.videos)} 条视频")

    def _remove_video(self, index):
        self.videos.pop(index)
        self._render_videos()

    def _clear_videos(self):
        if not self.running:
            self.videos.clear()
            self._render_videos()

    def _choose_music_folder(self):
        folder = filedialog.askdirectory(title="选择音乐文件夹", initialdir=self.music_folder.get() or None)
        if folder:
            self.music_folder.set(folder)
            self._save_config()

    def _toggle_image_controls(self):
        state = "normal" if self.use_images.get() else "disabled"
        self.image_entry.configure(state="readonly" if state == "normal" else "disabled")
        self.image_button.configure(state=state)
        self.outline_switch.configure(state=state)
        if state == "disabled":
            self.use_outline.set(False)

    def _choose_image_folder(self):
        folder = filedialog.askdirectory(title="选择透明图片文件夹", initialdir=self.image_folder.get() or None)
        if folder:
            self.image_folder.set(folder)
            self._save_config()

    def _start_export(self):
        if self.running:
            return
        if not self.videos:
            messagebox.showwarning(APP_NAME, "请先拖入至少一条视频。")
            return
        music = find_music(Path(self.music_folder.get()))
        if not music:
            messagebox.showwarning(APP_NAME, "请选择包含音乐的文件夹。")
            return
        assignments = assign_music(self.videos, music)
        image_by_video = {}
        if self.use_images.get():
            images = find_images(Path(self.image_folder.get()))
            if not images:
                messagebox.showwarning(APP_NAME, "所选图片文件夹中没有 PNG 或 WebP 图片。")
                return
            image_by_video = dict(assign_overlays(self.videos, images))
        jobs = [
            ExportJob(
                video,
                song,
                output_path_for(video),
                image_by_video.get(video, ()),
                self.use_outline.get(),
            )
            for video, song in assignments
        ]
        source_volume = self.source_volume.get() / 100
        music_volume = self.music_volume.get() / 100
        self.running = True
        self.export_button.configure(state="disabled", text="正在导出…")
        self.progress.set(0)
        thread = threading.Thread(
            target=self._export_worker,
            args=(jobs, source_volume, music_volume),
            daemon=True,
        )
        thread.start()

    def _export_worker(self, jobs, source_volume, music_volume):
        errors = []
        total = len(jobs)
        for index, job in enumerate(jobs):
            image_text = ""
            if job.overlays:
                image_text = "  ·  " + " + ".join(overlay.image.name for overlay in job.overlays)
            self.events.put(("status", f"{index + 1}/{total}  {job.video.name}  ·  {job.music.name}{image_text}"))
            try:
                export_job(
                    job,
                    source_volume=source_volume,
                    music_volume=music_volume,
                    progress=lambda value, i=index: self.events.put(("progress", (i + value) / total)),
                )
            except (MediaError, OSError) as exc:
                errors.append(f"{job.video.name}：{exc}")
        self.events.put(("done", jobs, errors))

    def _drain_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "status":
                    self.status_label.configure(text=event[1])
                elif event[0] == "progress":
                    self.progress.set(event[1])
                elif event[0] == "done":
                    self._finish_export(event[1], event[2])
                elif event[0] == "update_checked":
                    self._finish_update_check(event[1], event[2])
                elif event[0] == "update_error":
                    self._finish_update_error(event[1], event[2])
                elif event[0] == "update_progress":
                    self._set_update_progress(event[1], event[2])
                elif event[0] == "update_prepared":
                    self._finish_update_download(event[1])
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _check_updates(self, manual: bool):
        if self.checking_update:
            return
        self.checking_update = True
        self.update_button.configure(state="disabled", text="检查中…")

        def worker():
            try:
                release = fetch_latest_release(APP_VERSION)
                self.events.put(("update_checked", release, manual))
            except UpdateError as exc:
                self.events.put(("update_error", str(exc), manual))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_update_check(self, release: ReleaseInfo | None, manual: bool):
        self.checking_update = False
        self.update_button.configure(state="normal", text="检查更新")
        if release:
            self._show_update_dialog(release)
        elif manual:
            messagebox.showinfo(
                "检查更新",
                f"当前版本：v{APP_VERSION}\n最新版本：v{APP_VERSION}\n\n当前已是最新版本。",
            )

    def _finish_update_error(self, detail: str, visible: bool):
        self.checking_update = False
        self.update_button.configure(state="normal", text="检查更新")
        if self.update_action_button and self.update_action_button.winfo_exists():
            self.update_action_button.configure(state="normal", text="下载并安装")
        if visible:
            messagebox.showwarning(
                "检查更新",
                f"当前版本：v{APP_VERSION}\n\n{detail}\n\n网络异常不会影响视频处理功能。",
            )

    def _show_update_dialog(self, release: ReleaseInfo):
        if self.update_dialog and self.update_dialog.winfo_exists():
            self.update_dialog.destroy()
        dialog = ctk.CTkToplevel(self)
        self.update_dialog = dialog
        dialog.title("发现新版本")
        dialog.geometry("620x500")
        dialog.minsize(520, 420)
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(
            dialog,
            text="发现可用更新",
            font=("Microsoft YaHei UI", 20, "bold"),
            text_color="#17202a",
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 8))
        ctk.CTkLabel(
            dialog,
            text=f"当前版本：v{APP_VERSION}    最新版本：v{release.version}",
            font=("Microsoft YaHei UI", 13),
            text_color="#4d5966",
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 12))
        notes = ctk.CTkTextbox(dialog, font=("Microsoft YaHei UI", 13), wrap="word")
        notes.grid(row=2, column=0, sticky="nsew", padx=24)
        notes.insert("1.0", release.notes)
        notes.configure(state="disabled")
        self.update_progress = ctk.CTkProgressBar(dialog, height=8, progress_color="#237a57")
        self.update_progress.grid(row=3, column=0, sticky="ew", padx=24, pady=(14, 4))
        self.update_progress.set(0)
        self.update_status = ctk.CTkLabel(
            dialog, text="", anchor="w", font=("Microsoft YaHei UI", 12), text_color="#68707a"
        )
        self.update_status.grid(row=4, column=0, sticky="ew", padx=24)
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew", padx=24, pady=18)
        ctk.CTkButton(
            actions,
            text="发布页面",
            width=86,
            fg_color="transparent",
            hover_color="#eef0f2",
            text_color="#35404a",
            border_width=1,
            border_color="#cbd1d8",
            command=lambda: webbrowser.open(release.page_url),
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="稍后",
            width=72,
            fg_color="transparent",
            hover_color="#eef0f2",
            text_color="#35404a",
            command=dialog.destroy,
        ).pack(side="right")
        self.update_action_button = ctk.CTkButton(
            actions,
            text="下载并安装",
            width=116,
            fg_color="#237a57",
            hover_color="#1d684a",
            command=lambda: self._download_update(release),
        )
        self.update_action_button.pack(side="right", padx=8)

    def _download_update(self, release: ReleaseInfo):
        if self.running:
            messagebox.showwarning("安装更新", "请等待当前视频导出完成后再安装更新。")
            return
        self.update_action_button.configure(state="disabled", text="正在下载…")
        self.update_status.configure(text="正在下载并校验完整更新包…")

        def progress(downloaded: int, total: int):
            self.events.put(("update_progress", downloaded, total))

        def worker():
            try:
                prepared = prepare_update(release, progress)
                self.events.put(("update_prepared", prepared))
            except UpdateError as exc:
                self.events.put(("update_error", str(exc), True))

        threading.Thread(target=worker, daemon=True).start()

    def _set_update_progress(self, downloaded: int, total: int):
        if not self.update_dialog or not self.update_dialog.winfo_exists():
            return
        if total:
            self.update_progress.set(downloaded / total)
            self.update_status.configure(text=f"已下载 {downloaded / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MiB")
        else:
            self.update_status.configure(text=f"已下载 {downloaded / 1024 / 1024:.1f} MiB")

    def _finish_update_download(self, prepared: PreparedUpdate):
        if not messagebox.askyesno(
            "安装更新",
            f"v{prepared.release.version} 已下载并通过 SHA-256 校验。\n\n"
            "程序将退出，由独立更新助手替换整个安装目录；失败时会自动恢复旧版本。\n\n"
            "现在安装吗？",
        ):
            self.update_action_button.configure(state="normal", text="下载并安装")
            return
        try:
            install_prepared_update(prepared)
        except UpdateError as exc:
            self._finish_update_error(str(exc), True)
            return
        self.destroy()

    def _finish_export(self, jobs, errors):
        self.running = False
        self.export_button.configure(state="normal", text="开始批量导出")
        success = len(jobs) - len(errors)
        self.status_label.configure(text=f"完成：成功 {success} 条，失败 {len(errors)} 条")
        if errors:
            messagebox.showerror(APP_NAME, f"成功 {success} 条，失败 {len(errors)} 条：\n\n" + "\n".join(errors[:8]))
        else:
            output_folders = {job.output.parent for job in jobs}
            if len(output_folders) == 1:
                folder = next(iter(output_folders))
                if messagebox.askyesno(APP_NAME, f"全部 {success} 条视频已导出。\n\n是否打开“已配乐”文件夹？"):
                    os.startfile(folder)
            else:
                messagebox.showinfo(APP_NAME, f"全部 {success} 条视频已导出到各自的“已配乐”文件夹。")

    def _load_music_folder(self):
        return self._load_config().get("music_folder", "")

    def _load_config(self):
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_config(self):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(
                json.dumps(
                    {
                        "music_folder": self.music_folder.get(),
                        "image_folder": self.image_folder.get(),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass


if __name__ == "__main__":
    App().mainloop()
