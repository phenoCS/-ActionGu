# -*- coding: utf-8 -*-
"""
任务修仙计时器 —— 极简桌面自律工具
=================================
技术栈：Python + Tkinter（纯本地单机程序，禁止联网、无登录、无云同步）
核心思想：以「任务闭环」作为修行标准，单个任务专注累计 ≥5 分钟方可计入有效修行，
          集齐 3 个有效任务晋升一阶，境界体系严格采用《蛊真人》蛊师体系。

代码规范：关键位置均配有中文注释，方便后续二次修改。
"""

import os
import json
import time
import tkinter as tk
from tkinter import messagebox

# ====================== 常量配置 ======================
# data.json 存放于脚本所在目录，打包为 exe 后依然可用
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")

# 境界体系：严格按《蛊真人》蛊师体系，一转至九转，每转四阶，共 36 阶
_ZHUAN = ["一", "二", "三", "四", "五", "六", "七", "八", "九"]
_JIE = ["初阶", "中阶", "高阶", "巅峰"]
REALMS = [f"{z}转{j}" for z in _ZHUAN for j in _JIE]

VALID_TASK_SECONDS = 300    # 单个任务有效修行所需最短时长：5 分钟（300 秒）
ROUND_TARGET = 3            # 每轮需集齐的有效任务数量，集齐即晋升

# 测试模式：True 时把有效任务门槛降到 TEST_SECONDS 秒且不弹窗，便于快速验证晋升流程；
# 正式发布 / 日常使用请改为 False（恢复 5 分钟门槛与提示文案）。
TEST_MODE = True
TEST_SECONDS = 3

# 提示文案（按需求固定）
MSG_TOO_SHORT = "修行尚浅，还需要更多沉淀，不计入修行积累。"
MSG_PROMOTE = "些许风霜些许愁，无足之鸟不回头！"


def format_time(total_seconds):
    """将秒数格式化为 时:分:秒（HH:MM:SS，小时可超过 24）"""
    total = int(total_seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


class XiuXianTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("任务修仙计时器")
        self.root.geometry("760x540")
        self.root.resizable(False, False)

        # ---------- 持久化状态 ----------
        self.tasks = []             # 任务清单（字符串列表）
        self.realm_index = 0        # 当前境界索引
        self.round_count = 0        # 本轮已完成有效任务数（0~3）
        self.history_total = 0      # 历史累计有效任务总数

        self.selected_index = None  # 当前选中的任务索引（None 表示未选）

        # ---------- 计时器状态 ----------
        self.running = False        # 是否正在运行
        self.paused = False         # 是否处于暂停
        self.session_start = 0.0    # 当前计时段起点（time.time() 值）
        self.session_accum = 0.0    # 本段之前已累计的秒数（用于暂停后继续累加）
        self.after_id = None        # after 定时器回调 ID，用于取消

        self.load_data()            # 启动时加载本地数据
        self.build_ui()
        self.refresh_task_list()
        self.update_top_info()
        self.update_button_states()

        # 程序关闭时自动保存并清理定时器
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ====================== 本地持久化 ======================
    def load_data(self):
        """从 data.json 读取任务清单、当前境界、本轮计数、历史总数"""
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.tasks = data.get("tasks", [])
            self.realm_index = data.get("realm_index", 0)
            self.round_count = data.get("round_count", 0)
            self.history_total = data.get("history_total", 0)
            # 边界保护：索引越界时回退到合法范围
            if not (0 <= self.realm_index < len(REALMS)):
                self.realm_index = 0
        except (json.JSONDecodeError, OSError):
            # 文件损坏时静默忽略，使用默认空数据
            pass

    def save_data(self):
        """将当前状态写入 data.json（关闭程序或关键事件后调用）"""
        data = {
            "tasks": self.tasks,
            "realm_index": self.realm_index,
            "round_count": self.round_count,
            "history_total": self.history_total,
        }
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def on_close(self):
        """窗口关闭：停止计时、保存数据、销毁窗口"""
        self.stop_timer(quiet=True)
        self.save_data()
        self.root.destroy()

    # ====================== 界面构建 ======================
    def build_ui(self):
        """搭建整体界面：顶部信息栏 / 左侧任务列表 / 右侧计时器 / 底部理念"""
        # ---- 顶部固定信息栏 ----
        top = tk.Frame(self.root, bd=1, relief="raised")
        top.pack(side="top", fill="x", padx=6, pady=6)
        self.lbl_realm = tk.Label(top, text="", font=("Microsoft YaHei", 12, "bold"))
        self.lbl_round = tk.Label(top, text="", font=("Microsoft YaHei", 12))
        self.lbl_history = tk.Label(top, text="", font=("Microsoft YaHei", 12))
        self.lbl_realm.pack(side="left", padx=12)
        self.lbl_round.pack(side="left", padx=12)
        self.lbl_history.pack(side="left", padx=12)

        # ---- 主体：左右两栏 ----
        main = tk.Frame(self.root)
        main.pack(side="top", fill="both", expand=True, padx=6, pady=4)

        # ===== 左栏：任务列表 =====
        left = tk.Frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # 任务输入框 + 新增按钮
        input_row = tk.Frame(left)
        input_row.pack(side="top", fill="x")
        self.entry = tk.Entry(input_row, font=("Microsoft YaHei", 11))
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.add_task())  # 回车也可新增
        self.btn_add = tk.Button(input_row, text="新增任务", command=self.add_task)
        self.btn_add.pack(side="left", padx=(4, 0))

        # 可滚动的任务列表容器（Canvas + Scrollbar）
        list_outer = tk.Frame(left, bd=1, relief="sunken")
        list_outer.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.canvas = tk.Canvas(list_outer)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll = tk.Scrollbar(list_outer, orient="vertical", command=self.canvas.yview)
        self.scroll.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.list_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        # ===== 右栏：计时器 =====
        right = tk.Frame(main, bd=1, relief="sunken", width=250)
        right.pack(side="right", fill="y", padx=(6, 0))
        right.pack_propagate(False)

        tk.Label(right, text="当前修行任务", font=("Microsoft YaHei", 10)).pack(pady=(10, 0))
        self.lbl_current = tk.Label(right, text="未选择任务", font=("Microsoft YaHei", 11), wraplength=230)
        self.lbl_current.pack(pady=(2, 6))

        self.lbl_time = tk.Label(right, text="00:00:00", font=("Microsoft YaHei", 30, "bold"))
        self.lbl_time.pack(pady=(4, 12))

        # 计时器四个按钮
        self.btn_start = tk.Button(right, text="开始任务", command=self.start_timer, width=18)
        self.btn_pause = tk.Button(right, text="暂停", command=self.toggle_pause, width=18)
        self.btn_complete = tk.Button(right, text="完成任务", command=self.complete_task, width=18)
        self.btn_end = tk.Button(right, text="结束计时", command=self.end_timer, width=18)
        self.btn_start.pack(pady=3)
        self.btn_pause.pack(pady=3)
        self.btn_complete.pack(pady=3)
        self.btn_end.pack(pady=3)

        self.lbl_status = tk.Label(right, text="", font=("Microsoft YaHei", 9), fg="gray", wraplength=230)
        self.lbl_status.pack(pady=(10, 4))

        # ---- 底部：程序理念（小字） ----
        bottom = tk.Frame(self.root)
        bottom.pack(side="bottom", fill="x", padx=6, pady=(2, 6))
        philosophy = (
            "程序理念：市面上多数自律工具以时长衡量收获，容易催生假性努力。\n"
            "本工具以任务闭环作为修行标准，唯有切实完成目标，境界方能提升。\n"
            "修行体系取材《蛊真人》，一转起步，九转巅峰为凡世尽头。"
        )
        tk.Label(bottom, text=philosophy, font=("Microsoft YaHei", 8),
                 fg="gray", justify="left").pack(anchor="w")

    # ====================== 任务列表逻辑 ======================
    def add_task(self):
        """新增任务：读取输入框，非空则加入列表并保存"""
        name = self.entry.get().strip()
        if not name:
            return
        self.tasks.append(name)
        self.entry.delete(0, tk.END)
        self.refresh_task_list()
        self.save_data()  # 关键事件后保存

    def delete_task(self, index):
        """删除任务：修行中的任务不可删除，需先结束计时"""
        if index == self.selected_index and self.running:
            messagebox.showinfo("提示", "该任务正在修行中，请先结束计时再删除。")
            return
        if 0 <= index < len(self.tasks):
            del self.tasks[index]
            # 选中索引随列表变动调整
            if self.selected_index == index:
                self.selected_index = None
                self.lbl_current.config(text="未选择任务")
            elif self.selected_index is not None and self.selected_index > index:
                self.selected_index -= 1
            self.refresh_task_list()
            self.update_button_states()
            self.save_data()

    def refresh_task_list(self):
        """重建任务列表显示，每行含「任务名（可选中）」与「删除」按钮"""
        for w in self.list_frame.winfo_children():
            w.destroy()
        for i, name in enumerate(self.tasks):
            row = tk.Frame(self.list_frame)
            row.pack(side="top", fill="x", pady=1)
            is_sel = (i == self.selected_index)
            is_running = (self.running and i == self.selected_index)
            label_text = name + ("（修行中）" if is_running else "")
            bg = "lightblue" if is_sel else "SystemButtonFace"
            # 任务名按钮：点击即选中（修行中不可切换）
            b = tk.Button(row, text=label_text, anchor="w", bg=bg,
                          command=lambda idx=i: self.select_task(idx))
            b.pack(side="left", fill="x", expand=True)
            # 删除按钮
            del_btn = tk.Button(row, text="删除", width=6,
                                command=lambda idx=i: self.delete_task(idx))
            del_btn.pack(side="right")
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def select_task(self, index):
        """选中任务：同一时间只能运行一个计时器，修行中禁止切换任务"""
        if self.running:
            return
        if 0 <= index < len(self.tasks):
            self.selected_index = index
            self.lbl_current.config(text=self.tasks[index])
            self.refresh_task_list()
            self.update_button_states()

    # ====================== 计时器逻辑 ======================
    def get_elapsed(self):
        """计算当前计时段的累计秒数（含暂停前的累计）"""
        if not self.running:
            return 0.0
        if self.paused:
            return self.session_accum
        return self.session_accum + (time.time() - self.session_start)

    def start_timer(self):
        """开始任务：仅当选中任务且当前无运行中的计时器时可用"""
        if self.selected_index is None or self.running:
            return
        self.running = True
        self.paused = False
        self.session_accum = 0.0
        self.session_start = time.time()
        self.lbl_current.config(text=self.tasks[self.selected_index])
        self.lbl_status.config(text="修行开始，专注当下。")
        self.refresh_task_list()      # 显示「修行中」标记
        self.update_button_states()
        self.tick()                   # 启动计时刷新循环

    def tick(self):
        """每秒刷新一次计时显示"""
        if not self.running:
            return
        self.lbl_time.config(text=format_time(self.get_elapsed()))
        self.after_id = self.root.after(250, self.tick)

    def toggle_pause(self):
        """暂停 / 继续：暂停时停止累加，继续时从当前点重新计时"""
        if not self.running:
            return
        if not self.paused:
            # 进入暂停：把已流逝的时间固化到累计值
            self.paused = True
            self.session_accum += time.time() - self.session_start
            self.lbl_status.config(text="已暂停。")
        else:
            # 继续：重置计时段起点
            self.paused = False
            self.session_start = time.time()
            self.lbl_status.config(text="修行继续。")
        self.update_button_states()

    def complete_task(self):
        """完成任务：累计 ≥5 分钟计入有效修行；不足则弹窗提示且不计入"""
        if not self.running:
            return
        # 有效任务时长门槛：测试模式用 TEST_SECONDS，正式模式用 5 分钟
        threshold = TEST_SECONDS if TEST_MODE else VALID_TASK_SECONDS
        elapsed = self.get_elapsed()
        if elapsed < threshold:
            # 不足门槛：用状态栏提示（非弹窗，不打断操作），保留计时让用户继续积累
            tag = "【测试模式】" if TEST_MODE else ""
            self.lbl_status.config(text=f"{tag}{MSG_TOO_SHORT}（可继续积累）")
            return

        # 达到有效标准：计入并结束本次计时
        self.stop_timer(quiet=True)
        self.round_count += 1
        self.history_total += 1

        # 本轮集齐 3 个有效任务 → 晋升
        if self.round_count >= ROUND_TARGET:
            self.round_count = 0
            if self.realm_index < len(REALMS) - 1:
                self.realm_index += 1
                messagebox.showinfo("境界提升", MSG_PROMOTE)
            else:
                # 已达九转巅峰，凡世尽头
                messagebox.showinfo("境界提升", "已臻九转巅峰，凡世尽头。")

        self.lbl_status.config(text="修行任务达成，已计入积累。")
        self.update_top_info()
        self.update_button_states()
        self.refresh_task_list()
        self.save_data()  # 关键事件后保存

    def end_timer(self):
        """结束计时：停止本次计时，不计入修行积累"""
        if not self.running:
            return
        self.stop_timer(quiet=True)
        self.lbl_status.config(text="计时结束，本次不计入修行积累。")
        self.update_button_states()
        self.refresh_task_list()

    def stop_timer(self, quiet=False):
        """内部统一停止计时并复位显示（quiet 用于关闭程序时静默）"""
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.running = False
        self.paused = False
        self.session_accum = 0.0
        self.session_start = 0.0
        self.lbl_time.config(text="00:00:00")

    # ====================== 状态刷新 ======================
    def update_top_info(self):
        """顶部固定展示：当前境界 / 本轮有效任务 / 历史总数"""
        self.lbl_realm.config(text=f"当前境界：{REALMS[self.realm_index]}")
        self.lbl_round.config(text=f"本轮已完成有效任务（{self.round_count}/{ROUND_TARGET}）")
        self.lbl_history.config(text=f"历史累计有效任务总数：{self.history_total}")

    def update_button_states(self):
        """根据当前状态启用 / 禁用按钮，保持交互一致"""
        sel = self.selected_index is not None
        self.btn_start.config(state="normal" if (sel and not self.running) else "disabled")
        self.btn_pause.config(state="normal" if self.running else "disabled")
        self.btn_complete.config(state="normal" if self.running else "disabled")
        self.btn_end.config(state="normal" if self.running else "disabled")
        self.btn_pause.config(text="继续" if (self.running and self.paused) else "暂停")


def main():
    root = tk.Tk()
    # 统一使用支持中文的字体（Windows 下 Microsoft YaHei 较稳定）
    XiuXianTimer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
