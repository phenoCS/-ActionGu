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
import sys
import json
import time
import subprocess
import tkinter as tk
from tkinter import messagebox

# ====================== 常量配置 ======================
# data.json 存放目录：
#   - 以脚本运行时，使用脚本所在目录；
#   - 打包为单文件 exe 后，__file__ 会指向临时解压目录（_MEIPASS），
#     必须用 sys.executable 所在目录，否则数据会在程序退出后丢失。
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
ICON_FILE = os.path.join(BASE_DIR, "app.ico")   # 程序/快捷方式图标

# 境界体系：严格按《蛊真人》蛊师体系，一转至九转，每转四阶，共 36 阶
_ZHUAN = ["一", "二", "三", "四", "五", "六", "七", "八", "九"]
_JIE = ["初阶", "中阶", "高阶", "巅峰"]
REALMS = [f"{z}转{j}" for z in _ZHUAN for j in _JIE]

# 各境界的《蛊真人》气质描述（原创/归纳，可由用户校订），索引与 REALMS 一一对应
REALM_DESC = dict(zip(REALMS, [
    "初触蛊道，如稚童开窍，万物皆可作蛊。",
    "蛊力渐盈，筋骨生力，已非寻常凡躯。",
    "蛊虫相济，手段初成，山野之间可称好手。",
    "一转之极，气力雄浑，却仍是修行路上第一步。",
    "真元初凝，举手投足已暗含蛊威。",
    "力如奔马，蛊效叠加，战力倍增。",
    "蛊道小成，内外兼修，已能独行江湖。",
    "二转圆满，根基扎实，可窥更高之境。",
    "蛊虫随心，攻防如意，渐脱凡俗桎梏。",
    "真元如潮，蛊术多变，敌手难测深浅。",
    "蛊道渐通，一蛊一世界，威能初显。",
    "三转之巅，已非乡野凡人可比。",
    "蛊力化罡，护身自立，凶兽亦能搏杀。",
    "真元浩荡，蛊阵初布，能以一敌众。",
    "蛊道精进，手段通玄，声名可传一方。",
    "四转圆满，半步蛊师之尊。",
    "真元如渊，蛊威盖世，一方豪强。",
    "蛊术通神，翻江倒海，气吞山河。",
    "蛊道大宗，一言定生死，一念动乾坤。",
    "五转绝顶，人间巅峰，凡世无敌手。",
    "渡劫飞升，初成蛊仙，寿元悠长。",
    "仙蛊随身，呼风唤雨，超脱尘世。",
    "蛊道仙法，移山填海，法则初握。",
    "六转仙尊，福地之主，俯瞰人间。",
    "仙蛊合一，道痕加身，天地任逍遥。",
    "蛊仙大修，言出法随，气运加身。",
    "蛊道通幽，窥探命运，执掌一方天意。",
    "七转巅峰，仙域巨擘，众生仰止。",
    "仙尊之境，道痕如海，翻覆乾坤。",
    "蛊道至尊，演化天地，自成一方界。",
    "仙威浩荡，万古长存，俯视八荒。",
    "八转绝巅，只差一步，可窥九转无上。",
    "无上之始，超脱一切，已非凡圣可拟。",
    "道则随心，时空倒转，执掌轮回。",
    "蛊道极致，万法归一，与道同寿。",
    "九转之巅，凡世尽头，传说中的传说。",
]))

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


def format_duration_short(total_seconds):
    """将秒数格式化为简洁中文时长，如 3秒 / 5分12秒 / 1时2分3秒"""
    total = int(total_seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h:
        return f"{h}时{m}分{s}秒"
    if m:
        return f"{m}分{s}秒"
    return f"{s}秒"


class XiuXianTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("任务修仙计时器")
        self.root.geometry("760x540")
        self.root.resizable(False, False)

        # ---------- 持久化状态 ----------
        self.tasks = []             # 任务清单：结构为 {"name","completed","first_duration","first_time"}
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
            # 兼容迁移：旧版 data.json 中 tasks 为字符串列表，这里统一升级为字典结构
            raw_tasks = data.get("tasks", [])
            self.tasks = []
            for t in raw_tasks:
                if isinstance(t, str):
                    self.tasks.append({"name": t, "completed": False, "first_duration": 0, "first_time": 0})
                elif isinstance(t, dict):
                    self.tasks.append({
                        "name": t.get("name", ""),
                        "completed": t.get("completed", False),
                        "first_duration": t.get("first_duration", 0),
                        "first_time": t.get("first_time", 0),
                    })
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

        # 当前境界的《蛊真人》描述（顶部境界名下方一行小字，沉浸感更强）
        desc_bar = tk.Frame(self.root)
        desc_bar.pack(side="top", fill="x", padx=6)
        self.lbl_realm_desc = tk.Label(
            desc_bar, text="", font=("Microsoft YaHei", 9, "italic"),
            fg="#555555", anchor="w",
        )
        self.lbl_realm_desc.pack(fill="x", padx=12, pady=(0, 4))
        self.lbl_realm = tk.Label(top, text="", font=("Microsoft YaHei", 12, "bold"))
        self.lbl_round = tk.Label(top, text="", font=("Microsoft YaHei", 12))
        self.lbl_history = tk.Label(top, text="", font=("Microsoft YaHei", 12))
        self.lbl_realm.pack(side="left", padx=12)
        self.lbl_round.pack(side="left", padx=12)
        self.lbl_history.pack(side="left", padx=12)

        # 桌面快捷方式：点击在用户桌面生成指向「启动.bat」的 .lnk（可重复点击）
        self.btn_shortcut = tk.Button(top, text="桌面快捷方式", command=self.create_desktop_shortcut)
        self.btn_shortcut.pack(side="right", padx=12)
        # 一键归零：清空全部任务与修行进度（破坏性操作，点击后需二次确认）
        self.btn_reset = tk.Button(top, text="重置", command=self.reset_all)
        self.btn_reset.pack(side="right", padx=12)

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
        self.tasks.append({
            "name": name,
            "completed": False,
            "first_duration": 0,
            "first_time": 0,
        })
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
        """重建任务列表显示：已完成任务显示绿色对勾与首次耗时，修行中追加标记"""
        for w in self.list_frame.winfo_children():
            w.destroy()
        for i, task in enumerate(self.tasks):
            name = task.get("name", "")
            completed = task.get("completed", False)
            first_dur = task.get("first_duration", 0)
            row = tk.Frame(self.list_frame)
            row.pack(side="top", fill="x", pady=1)
            is_sel = (i == self.selected_index)
            is_running = (self.running and i == self.selected_index)

            # 文本：已完成显示绿色对勾 + 首次耗时；修行中追加标记
            prefix = "✓ " if completed else ""
            dur_txt = f"　花费{format_duration_short(first_dur)}" if completed else ""
            run_txt = "（修行中）" if is_running else ""
            label_text = f"{prefix}{name}{dur_txt}{run_txt}"

            bg = "lightblue" if is_sel else "SystemButtonFace"
            fg = "green" if completed else "black"
            # 任务名按钮：点击即选中（修行中不可切换）
            b = tk.Button(row, text=label_text, anchor="w", bg=bg, fg=fg,
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
            self.lbl_current.config(text=self.tasks[index]["name"])
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
        self.lbl_current.config(text=self.tasks[self.selected_index]["name"])
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
        # 首次有效完成才记录「对勾 + 耗时」，后续重刷进度不覆盖初次记录
        task = self.tasks[self.selected_index]
        if not task.get("completed", False):
            task["completed"] = True
            task["first_duration"] = int(elapsed)
            task["first_time"] = time.time()
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

    def reset_all(self):
        """一键归零：清空全部任务与修行进度。

        属于破坏性、不可逆操作，因此点击后会弹出二次确认框，
        明确告知将清空的内容，需用户再次确认才真正执行。
        """
        # 二次确认：列出后果并强调不可恢复，避免误点造成损失
        confirm = messagebox.askyesno(
            "确认归零",
            "此操作将彻底清空以下内容，且无法恢复：\n"
            "  · 全部任务列表\n"
            "  · 当前境界（回到一转初阶）\n"
            "  · 本轮进度与历史累计总数\n\n"
            "确定要归零、从头开始修行吗？"
        )
        if not confirm:
            return
        # 若正在修行，先安全停止计时再清空，避免状态残留
        if self.running:
            self.stop_timer(quiet=True)
        # 全部归零
        self.tasks = []
        self.realm_index = 0
        self.round_count = 0
        self.history_total = 0
        self.selected_index = None
        self.lbl_current.config(text="未选择任务")
        self.lbl_status.config(text="已归零，修行从头开始。")
        self.refresh_task_list()
        self.update_top_info()
        self.update_button_states()
        self.save_data()  # 关键事件后保存，确保落盘

    def create_desktop_shortcut(self):
        """在用户桌面创建指向「启动.bat」的快捷方式（.lnk），可重复点击、已存在则覆盖。"""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.isdir(desktop):
                desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
            target = os.path.join(BASE_DIR, "启动.bat")
            lnk = os.path.join(desktop, "任务修仙计时器.lnk")
            ico = ICON_FILE
            # 用 PowerShell 的 WScript.Shell 创建 .lnk（避免额外依赖）
            ps = (
                "$ws = New-Object -ComObject WScript.Shell;"
                "$s = $ws.CreateShortcut('%s');"
                "$s.TargetPath = '%s';"
                "$s.WorkingDirectory = '%s';"
                "$s.Description = '任务修仙计时器';"
                "if (Test-Path '%s') { $s.IconLocation = '%s' };"
                "$s.Save()"
            ) % (lnk, target, BASE_DIR, ico, ico)
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                check=True,
            )
            messagebox.showinfo("成功", f"已在桌面创建快捷方式：\n{lnk}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("创建失败", f"无法创建桌面快捷方式：\n{exc}")

    # ====================== 状态刷新 ======================
    def update_top_info(self):
        """顶部固定展示：当前境界 / 本轮有效任务 / 历史总数"""
        self.lbl_realm.config(text=f"当前境界：{REALMS[self.realm_index]}")
        if REALM_DESC:
            self.lbl_realm_desc.config(text=REALM_DESC[REALMS[self.realm_index]])
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
    if os.path.exists(ICON_FILE):
        try:
            root.iconbitmap(ICON_FILE)
        except Exception:
            pass
    XiuXianTimer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
