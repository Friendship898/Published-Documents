from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from main import format_log, run_batch
from processor import ProcessResult


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PNG 红转橙批量工具 v2")
        self.root.geometry("920x620")

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.target_var = tk.StringVar(value="#FF8A00")
        self.mode_var = tk.StringVar(value="semantic_soft_recolor")
        self.recursive_var = tk.BooleanVar(value=True)
        self.dry_run_var = tk.BooleanVar(value=False)
        self.preview_mask_var = tk.BooleanVar(value=False)
        self.workers_var = tk.IntVar(value=4)
        self.preview_var = tk.IntVar(value=5)
        self.max_files_var = tk.IntVar(value=0)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.running = False

        self._build_ui()
        self._poll_logs()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="输入目录").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(frame, textvariable=self.input_var, width=72).grid(row=0, column=1, sticky=tk.EW, pady=4)
        ttk.Button(frame, text="选择", command=self._choose_input).grid(row=0, column=2, padx=6)

        ttk.Label(frame, text="输出目录").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(frame, textvariable=self.output_var, width=72).grid(row=1, column=1, sticky=tk.EW, pady=4)
        ttk.Button(frame, text="选择", command=self._choose_output).grid(row=1, column=2, padx=6)

        ttk.Label(frame, text="目标颜色").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Entry(frame, textvariable=self.target_var, width=20).grid(row=2, column=1, sticky=tk.W, pady=4)

        ttk.Label(frame, text="模式").grid(row=3, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(
            frame,
            textvariable=self.mode_var,
            values=["semantic_soft_recolor"],
            state="readonly",
            width=28,
        ).grid(row=3, column=1, sticky=tk.W, pady=4)

        opts = ttk.Frame(frame)
        opts.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=8)
        ttk.Checkbutton(opts, text="递归扫描", variable=self.recursive_var).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(opts, text="Dry Run", variable=self.dry_run_var).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(opts, text="输出掩码预览", variable=self.preview_mask_var).pack(side=tk.LEFT, padx=(0, 16))

        nums = ttk.Frame(frame)
        nums.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=4)
        ttk.Label(nums, text="并发数").pack(side=tk.LEFT)
        ttk.Spinbox(nums, from_=1, to=64, textvariable=self.workers_var, width=6).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(nums, text="预览数量").pack(side=tk.LEFT)
        ttk.Spinbox(nums, from_=0, to=200, textvariable=self.preview_var, width=6).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(nums, text="最大处理文件(0=全部)").pack(side=tk.LEFT)
        ttk.Spinbox(nums, from_=0, to=100000, textvariable=self.max_files_var, width=8).pack(side=tk.LEFT, padx=(4, 12))

        btns = ttk.Frame(frame)
        btns.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(4, 10))
        self.start_btn = ttk.Button(btns, text="开始处理", command=self._start)
        self.start_btn.pack(side=tk.LEFT)
        ttk.Button(btns, text="清空日志", command=self._clear_log).pack(side=tk.LEFT, padx=8)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(frame, textvariable=self.status_var).grid(row=7, column=0, columnspan=3, sticky=tk.W)

        self.log_text = tk.Text(frame, height=22, wrap=tk.NONE)
        self.log_text.grid(row=8, column=0, columnspan=3, sticky=tk.NSEW, pady=(8, 0))

        scroll_y = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scroll_y.grid(row=8, column=3, sticky=tk.NS, pady=(8, 0))
        self.log_text.configure(yscrollcommand=scroll_y.set)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(8, weight=1)

    def _choose_input(self) -> None:
        selected = filedialog.askdirectory(title="选择输入目录")
        if selected:
            self.input_var.set(selected)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="选择输出目录")
        if selected:
            self.output_var.set(selected)

    def _append_log(self, text: str) -> None:
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _poll_logs(self) -> None:
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_logs)

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def _start(self) -> None:
        if self.running:
            return

        input_dir = Path(self.input_var.get().strip())
        output_dir = Path(self.output_var.get().strip())
        target = self.target_var.get().strip()

        if not input_dir.exists() or not input_dir.is_dir():
            messagebox.showerror("错误", "输入目录不存在")
            return
        if not self.output_var.get().strip():
            messagebox.showerror("错误", "请设置输出目录")
            return
        if len(target.lstrip("#")) != 6:
            messagebox.showerror("错误", "目标颜色需为 6 位十六进制，例如 #FF8A00")
            return

        self.running = True
        self.start_btn.configure(state=tk.DISABLED)
        self.status_var.set("处理中...")

        worker = threading.Thread(
            target=self._run_job,
            args=(
                input_dir,
                output_dir,
                target,
                self.mode_var.get(),
                self.recursive_var.get(),
                self.dry_run_var.get(),
                self.preview_mask_var.get(),
                int(self.workers_var.get()),
                int(self.preview_var.get()),
                int(self.max_files_var.get()),
            ),
            daemon=True,
        )
        worker.start()

    def _run_job(
        self,
        input_dir: Path,
        output_dir: Path,
        target: str,
        mode: str,
        recursive: bool,
        dry_run: bool,
        preview_mask: bool,
        workers: int,
        preview_count: int,
        max_files: int,
    ) -> None:
        try:
            self.log_queue.put(
                f"开始任务: mode={mode} input={input_dir} output={output_dir} target={target} recursive={recursive} dry_run={dry_run} workers={workers} preview={preview_count} max_files={max_files}"
            )

            def on_result(result: ProcessResult) -> None:
                self.log_queue.put(format_log(result))

            summary = run_batch(
                input_dir=input_dir,
                output_dir=output_dir,
                target_color=target,
                mode=mode,
                recursive=recursive,
                dry_run=dry_run,
                workers=workers,
                preview_count=max(0, preview_count),
                preview_mask=preview_mask,
                max_files=max(0, max_files),
                on_result=on_result,
            )
            self.log_queue.put(
                f"完成: total={summary.total} processed={summary.processed} skipped={summary.skipped} failed={summary.failed}"
            )
            self.root.after(
                0,
                lambda: self.status_var.set(
                    f"完成：processed={summary.processed}, skipped={summary.skipped}, failed={summary.failed}"
                ),
            )
        except Exception as exc:
            self.log_queue.put(f"任务失败: {exc}")
            self.root.after(0, lambda: self.status_var.set("失败"))
        finally:
            self.running = False
            self.root.after(0, lambda: self.start_btn.configure(state=tk.NORMAL))


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
