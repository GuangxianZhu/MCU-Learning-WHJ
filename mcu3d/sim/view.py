"""芯片内部模拟器的画面。

中间是 Logisim 风格的电路图（见 schem/）：可以从整颗芯片一层层双击进去，
一直看到 ALU 里的全加器、寄存器里的与非门。导线按电平上色。
右边是数据面板：C 代码 / 汇编 / 机器码、寄存器表、内存表。
下方是“这一拍”说明、总线上的信号，以及 ALU 一位一位的计算过程。

CPU 每执行一条指令会产生若干“拍”（见 machine.Beat），这里按拍播放：
每一拍的前半拍时钟 CLK=0，后半拍 CLK=1，电路图跟着变色。
"""

from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode

from .. import theme
from ..schem.nav import Schematic
from ..schem.state import State
from ..ui import colored, wrap
from .asm import REG_NAMES
from .machine import (FLASH_BASE, SRAM_BASE, STACK_TOP, Machine, REGION_NAMES,
                      hex32, region_of, show_value)
from .programs import ORDER, PROGRAMS

SPEEDS = [0.25, 0.5, 1, 2, 4, 8]
BEAT_TIME = {"fetch": 1.5, "mem_read": 1.5, "mem_write": 1.5, "alu": 1.3,
             "decode": 1.0, "read_reg": 0.8, "write_reg": 0.8, "branch": 1.0,
             "calc": 0.8, "idle": 0.6, "fault": 1.0}
KIND_NAMES = {"fetch": "取指", "decode": "译码", "read_reg": "读寄存器", "alu": "ALU 运算",
              "mem_read": "读存储器", "mem_write": "写存储器", "write_reg": "写回寄存器",
              "branch": "改 PC", "calc": "算地址", "idle": "空转", "fault": "出错"}

# 右侧数据面板（aspect2d 单位，相对右上角）
RW = 1.24
RX = -RW - 0.02
SCALE = 0.027


def _frame(parent, x0, x1, z0, z1, alpha=0.82):
    return DirectFrame(parent=parent, frameColor=(0.04, 0.05, 0.08, alpha),
                       frameSize=(x0, x1, z0, z1))


def _text(parent, pos, scale=SCALE, fg=theme.TEXT, align=TextNode.ALeft):
    from ..ui import get_font
    return OnscreenText(parent=parent, pos=pos, scale=scale, align=align, font=get_font(),
                        fg=fg, mayChange=True, text="")


class Panels:
    """右侧与下方的 2D 数据面板。"""

    def __init__(self, app):
        self.app = app
        from ..ui import get_font
        self.lh = SCALE * get_font().getLineHeight()
        tr = app.a2dTopRight
        self.frames = []

        # ---- 代码面板 ----
        self.code_top = -0.15
        f = _frame(tr, RX, -0.02, -0.98, self.code_top)
        self.frames.append(f)
        t = _text(f, (RX + 0.02, self.code_top - 0.04), 0.03, theme.ACCENT)
        t.setText("C 代码")
        self.prog_title = t
        t2 = _text(f, (RX + 0.62, self.code_top - 0.04), 0.03, theme.ACCENT)
        t2.setText("地址        机器码    汇编指令")
        self.code_row0 = self.code_top - 0.09
        self.c_bar = DirectFrame(parent=f, frameColor=(0.25, 0.3, 0.5, 0.9),
                                 frameSize=(RX + 0.01, RX + 0.6, 0, self.lh))
        self.asm_bar = DirectFrame(parent=f, frameColor=(0.25, 0.3, 0.5, 0.9),
                                   frameSize=(RX + 0.61, -0.03, 0, self.lh))
        self.c_text = _text(f, (RX + 0.02, self.code_row0))
        self.asm_text = _text(f, (RX + 0.62, self.code_row0))

        # ---- 寄存器表 ----
        top = -1.0
        f = _frame(tr, RX, -0.02, -1.43, top)
        self.frames.append(f)
        _text(f, (RX + 0.02, top - 0.04), 0.03, theme.ACCENT).setText(
            "CPU 寄存器（括号里是十进制）")
        self.reg_row0 = top - 0.085
        self.reg_bars = []
        for i in range(16):
            x0 = RX + 0.01 + (i // 8) * 0.61
            bar = DirectFrame(parent=f, frameColor=(0, 0, 0, 0),
                              frameSize=(x0, x0 + 0.6, 0, self.lh))
            bar.setZ(self.reg_row0 - (i % 8) * self.lh - self.lh * 0.28)
            self.reg_bars.append([bar, 0.0, None])
        self.reg_texts = [_text(f, (RX + 0.02, self.reg_row0)),
                          _text(f, (RX + 0.63, self.reg_row0))]
        self.flag_text = _text(f, (RX + 0.02, self.reg_row0 - 8 * self.lh))

        # ---- 内存表 ----
        top = -1.45
        f = _frame(tr, RX, -0.02, -1.98, top)
        self.frames.append(f)
        self.mem_title = _text(f, (RX + 0.02, top - 0.04), 0.03, theme.ACCENT)
        self.mem_row0 = top - 0.085
        self.mem_rows = 11
        self.mem_bars = []
        for k in range(self.mem_rows):
            bar = DirectFrame(parent=f, frameColor=(0, 0, 0, 0),
                              frameSize=(RX + 0.01, -0.03, 0, self.lh))
            bar.setZ(self.mem_row0 - k * self.lh - self.lh * 0.28)
            self.mem_bars.append([bar, 0.0, None])
        self.mem_cols = [_text(f, (RX + 0.02, self.mem_row0)),
                         _text(f, (RX + 0.27, self.mem_row0)),
                         _text(f, (RX + 0.52, self.mem_row0))]

        # ---- 下方：这一拍 + 总线信号 + ALU ----
        bc = app.a2dBottomCenter
        from ..app import SIM_PANEL_W
        aspect = app.getAspectRatio()
        self.strip_w = W = max(0.8, min(1.6, 2 * aspect - SIM_PANEL_W - RW - 0.08))
        cx = (SIM_PANEL_W - RW - 0.02) / 2
        x0 = cx - W / 2
        self.strip_x0 = x0
        f = _frame(bc, x0, x0 + W, 0.02, 0.5)
        self.frames.append(f)
        self.status = _text(f, (x0 + 0.02, 0.46), 0.028, theme.ACCENT)
        self.beat_text = _text(f, (x0 + 0.02, 0.42), 0.028)
        self.bus_text = _text(f, (x0 + 0.02, 0.33), 0.026)
        self.alu_labels = _text(f, (x0 + 0.02, 0.255), 0.026, theme.TEXT_DIM)
        self.alu_bits = _text(f, (x0 + 0.16, 0.255), 0.026)
        self.alu_dec = _text(f, (x0 + W - 0.02, 0.255), 0.026, theme.TEXT_DIM,
                             TextNode.ARight)
        self.alu_flags = _text(f, (x0 + 0.02, 0.255 - 4 * 0.026 * 1.35), 0.026)

    def destroy(self):
        for f in self.frames:
            f.destroy()

    def set_visible(self, on):
        for f in self.frames:
            f.show() if on else f.hide()

    # ---- 代码 ----
    def set_code(self, c_rows, asm_rows):
        self.c_text.setText("\n".join(c_rows))
        self.asm_text.setText("\n".join(asm_rows))

    def set_code_bars(self, c_row, asm_row, executing):
        color = (0.55, 0.32, 0.1, 0.95) if executing else (0.22, 0.27, 0.45, 0.95)
        for bar, row in ((self.c_bar, c_row), (self.asm_bar, asm_row)):
            if row is None:
                bar.hide()
                continue
            bar.show()
            bar["frameColor"] = color
            bar.setZ(self.code_row0 - row * self.lh - self.lh * 0.28)

    # ---- 高亮衰减 ----
    def mark(self, bars, i, color, t=1.2):
        bars[i][1] = t
        bars[i][2] = color

    def update(self, dt):
        for bars in (self.reg_bars, self.mem_bars):
            for item in bars:
                bar, t, color = item
                if t <= 0:
                    continue
                item[1] = t - dt
                a = max(0.0, min(1.0, item[1] / 0.6)) * 0.85
                bar["frameColor"] = (color[0], color[1], color[2], a)


class SimView:
    """模拟器：一台 Machine + 分层电路图 + 2D 面板 + 播放控制。

    lesson 需要提供 root、app、make_pickable（Lesson 基类都有）。
    sheet 是一开始显示哪一层电路图（chip / cpu / alu / regfile）。
    """

    def __init__(self, lesson, program="inc", on_beat=None, sheet="chip"):
        self.lesson = lesson
        self.app = lesson.app
        self.panels = Panels(self.app)
        self.schem = Schematic(lesson, sheet, (self.panels.strip_x0, self.panels.strip_w))
        self.on_beat = on_beat
        self.speed_i = 2
        self.running = False
        self.mem_mode = "auto"
        self.mem_focus = "flash"
        self.load(program)

    def destroy(self):
        self.schem.destroy()
        self.panels.destroy()

    # ------------------------------------------------------------ 程序
    def load(self, key):
        self.program = PROGRAMS[key]
        self.machine = Machine(self.program)
        self._build_code_rows()
        self.reset()

    def reset(self):
        self.machine.reset()
        self.queue = []
        self.cur = None
        self.cur_t = 0.0
        self.cur_len = 0.0
        self.instr_beats = 0
        self.instr_addr = None
        self.mem_hidden = {}
        self.shown_r = list(self.machine.cpu.r)
        self.shown_flags = dict(self.machine.cpu.flags)
        self.last_alu = None
        self.last_bus = None
        self.fault = None
        # 电路图要用的：最近显示的一拍、时钟、IR 里的机器码、CPU 内部各条线最后的值
        self.show_beat = None
        self.clk = 0
        self.last_ir = None
        self.last_asm = ""
        self.hold = {}
        self.last_text = ("按空格执行一条指令，按 T 只走一拍。第一步是“复位”："
                          "CPU 先从向量表读出 SP 和 PC。")
        self.running = False
        self.single = False
        self.refresh_all()
        self.push_state()

    def state(self):
        return State(beat=self.show_beat, active=self.cur is not None and
                     self.cur is self.show_beat, clk=self.clk, regs=list(self.shown_r),
                     flags=dict(self.shown_flags), need_reset=self.machine.cpu.need_reset,
                     alu=self.last_alu, ir=self.last_ir, asm=self.last_asm, hold=dict(self.hold))

    def push_state(self):
        self.schem.apply(self.state())

    def _build_code_rows(self):
        p = self.program
        self.c_rows = [line if line.strip() else " " for line in p.c_lines]
        rows, self.row_of_line, self.line_c = [], {}, {}
        for i, ln in enumerate(p.lines):
            if ln.label:
                rows.append(colored("dim", ln.text))
                continue
            self.row_of_line[i] = len(rows)
            code = " ".join("%04X" % c for c in ln.code)
            rows.append("%s   %-9s  %s" % (_addr(ln.addr), code, ln.text))
        for addr, value, what in p.literals:
            rows.append(colored("dim", "%s   %08X   .word（%s）" % (_addr(addr), value, what)))
        self.asm_rows = rows
        self.names = p.names()

    # ------------------------------------------------------------ 控制
    def bind_keys(self, lesson, programs=None):
        """绑定播放按键。programs 不为空时，数字键 1~n 切换例程。"""
        lesson.accept("space", self.step_instruction)
        lesson.accept("t", self.step_beat)
        lesson.accept("r", self.toggle_run)
        lesson.accept("z", self.reset)
        lesson.accept("m", self.next_mem_mode)
        lesson.accept("backspace", self.schem.up)
        lesson.accept("enter", self.schem.enter)
        lesson.accept_keys(["arrow_up"], self.change_speed, [1])
        lesson.accept_keys(["arrow_down"], self.change_speed, [-1])
        for k, key in enumerate(programs or []):
            lesson.accept(str(k + 1), self.load, [key])

    def change_speed(self, d):
        self.speed_i = max(0, min(len(SPEEDS) - 1, self.speed_i + d))
        self.refresh_status()

    def toggle_run(self):
        self.running = not self.running
        if self.running and not self.queue and self.cur is None:
            self._start_instruction()
        self.refresh_status()

    def step_instruction(self):
        """空格：正在播放就直接播完这条；否则开始下一条并完整播放。"""
        self.running = False
        if self.cur is not None or self.queue:
            self._finish_instruction()
            return
        self._start_instruction()
        self.single = False

    def step_beat(self):
        self.running = False
        if self.cur is not None:
            self._end_beat()
        if not self.queue:
            self._commit_instruction()
            self._start_instruction(play=False)
        if self.queue:
            self._begin_beat(self.queue.pop(0))
            self.single = True
        self.refresh_status()

    def next_mem_mode(self):
        modes = ["auto", "flash", "vars", "stack"]
        self.mem_mode = modes[(modes.index(self.mem_mode) + 1) % len(modes)]
        self.refresh_mem()

    # ------------------------------------------------------------ 播放
    def _start_instruction(self, play=True):
        if self.fault:
            self.last_text = self.fault + "（按 Z 复位重来）"
            self.refresh_status()
            return
        cpu = self.machine.cpu
        self.shown_r = list(cpu.r)
        self.shown_flags = dict(cpu.flags)
        self.instr_addr = None if cpu.need_reset else cpu.r[15]
        beats = self.machine.step()
        self.mem_hidden = {}
        for b in beats:
            if b.kind == "mem_write" and (b.addr & ~3) not in self.mem_hidden:
                self.mem_hidden[b.addr & ~3] = self._old_word(b)
        self.queue = beats
        self.instr_beats = len(beats)
        self.single = not play
        self.refresh_code()
        if play and self.queue:
            self._begin_beat(self.queue.pop(0))

    def _old_word(self, b):
        cur = self.machine.bus.peek(b.addr & ~3) or 0
        if b.size == 4:
            return b.old if b.old is not None else 0
        shift = (b.addr & 3) * 8
        return cur & ~(0xFF << shift) | ((b.old or 0) << shift)

    def _finish_instruction(self):
        if self.cur is not None:
            self._end_beat()
        while self.queue:
            b = self.queue.pop(0)
            self._begin_beat(b)
            self._end_beat()
        self._commit_instruction()

    def _commit_instruction(self):
        cpu = self.machine.cpu
        self.shown_r = list(cpu.r)
        self.shown_flags = dict(cpu.flags)
        self.mem_hidden = {}
        self.instr_addr = None
        self.refresh_all()
        self.push_state()

    def _begin_beat(self, b):
        self.cur = b
        self.cur_t = 0.0
        self.cur_len = BEAT_TIME.get(b.kind, 0.8)
        self.last_text = b.text
        self.show_beat = b
        self.clk = 0
        dur = self.cur_len / SPEEDS[self.speed_i]
        k = b.kind
        h = self.hold
        if k == "fetch":
            self.mem_focus = "flash"
            self.last_bus = (b.addr, b.value, "read", "取指")
            self.last_ir = (b.value, b.size)
            self.last_asm = ""
            self.refresh_code()
            self.refresh_mem(highlight=(b.addr & ~3, (0.2, 0.45, 0.9)))
        elif k == "decode":
            self.last_asm = b.asm
        elif k == "read_reg":
            h["sel_a"], h["rf_a"] = b.regs[0], self.shown_r[b.regs[0]]
            if len(b.regs) > 1:
                h["sel_b"], h["rf_b"] = b.regs[1], self.shown_r[b.regs[1]]
            for r in b.regs:
                self.panels.mark(self.panels.reg_bars, r, (0.2, 0.45, 0.9), dur + 0.4)
        elif k == "alu":
            self.last_alu = b
            h["y"] = b.result
            self.refresh_alu()
        elif k in ("mem_read", "mem_write"):
            read = k == "mem_read"
            h["y"] = b.addr
            self._focus_mem(b.addr)
            self.last_bus = (b.addr, b.value, "read" if read else "write",
                             "读数据" if read else "写数据")
            self.refresh_mem(highlight=(b.addr & ~3, (0.2, 0.45, 0.9) if read else None))
        elif k == "write_reg":
            self.shown_r[b.reg] = b.new
            self.panels.mark(self.panels.reg_bars, b.reg, (0.85, 0.45, 0.1), dur + 0.6)
            self.refresh_regs()
        elif k == "branch":
            h["y"] = b.target
        elif k == "calc" and self.queue and self.queue[0].kind in ("mem_read", "mem_write"):
            h["y"] = self.queue[0].addr      # 这一拍 ALU 算的就是下一拍要访问的地址
        elif k == "fault":
            self.fault = b.text
            self.running = False
        if self.on_beat:
            self.on_beat(b)
        self.refresh_status()
        self.push_state()

    def _end_beat(self):
        b = self.cur
        self.cur = None
        if b is None:
            return
        self.clk = 1
        k = b.kind
        if k == "fetch":
            self.shown_r[15] = b.next_pc
            self.refresh_regs()
        elif k == "alu":
            if b.set_flags:
                self.shown_flags = dict(b.flags_new)
                self.refresh_regs()
        elif k == "mem_write":
            self.mem_hidden.pop(b.addr & ~3, None)
            self.refresh_mem(highlight=(b.addr & ~3, (0.85, 0.45, 0.1)))
        elif k == "branch":
            if b.taken:
                self.shown_r[15] = b.target
                self.panels.mark(self.panels.reg_bars, 15, (0.85, 0.45, 0.1), 1.0)
                self.refresh_regs()
        self.push_state()

    def _focus_mem(self, addr):
        reg = region_of(addr)
        if reg == "flash":
            self.mem_focus = "flash"
        elif reg == "sram":
            self.mem_focus = "stack" if addr >= self.shown_r[13] - 16 and addr >= \
                STACK_TOP - 0x400 else "vars"

    def update(self, dt):
        self.panels.update(dt)
        if self.cur is not None:
            self.cur_t += dt * SPEEDS[self.speed_i]
            if self.clk == 0 and self.cur_t >= self.cur_len / 2:
                self.clk = 1          # 后半拍：时钟上升沿，寄存器存下新值
                self.push_state()
            if self.cur_t >= self.cur_len:
                self._end_beat()
                if self.queue and not self.single:
                    self._begin_beat(self.queue.pop(0))
                elif not self.queue:
                    if not self.single:
                        self._commit_instruction()
                    if self.running:
                        self._start_instruction()
                self.refresh_status()
        elif self.running:
            if self.queue:
                self._begin_beat(self.queue.pop(0))
            else:
                self._commit_instruction()
                self._start_instruction()

    # ------------------------------------------------------------ 面板刷新
    def refresh_all(self):
        self.refresh_code()
        self.refresh_regs()
        self.refresh_mem()
        self.refresh_alu()
        self.refresh_status()

    def refresh_code(self):
        p = self.program
        executing = self.instr_addr is not None
        addr = self.instr_addr if executing else self.machine.cpu.r[15]
        if self.machine.cpu.need_reset:
            addr = None
        line = p.line_at(addr) if addr is not None else None
        asm_row = self.row_of_line.get(line)
        c_row = p.lines[line].c_line if line is not None else None
        self.panels.prog_title.setText("C 代码 · 例程：%s" % p.title)
        self.panels.set_code(self.c_rows, self.asm_rows)
        self.panels.set_code_bars(c_row, asm_row, executing)

    def refresh_regs(self):
        r = self.shown_r
        cols = []
        for half in range(2):
            rows = []
            for i in range(half * 8, half * 8 + 8):
                v = r[i]
                dec = show_value(v)
                dec = "" if dec.startswith("0x") else "（%s）" % dec
                rows.append("%-3s %s %s" % (REG_NAMES[i], hex32(v), colored("dim", dec)))
            cols.append("\n".join(rows))
        for t, s in zip(self.panels.reg_texts, cols):
            t.setText(s)
        f = self.shown_flags
        bits = "   ".join(colored("hi" if f[k] else "dim", "%s=%d" % (k, f[k])) for k in "NZCV")
        self.panels.flag_text.setText("标志位  " + bits)

    def refresh_mem(self, highlight=None):
        mode = self.mem_focus if self.mem_mode == "auto" else self.mem_mode
        bus = self.machine.bus
        sp = self.shown_r[13]
        n = self.panels.mem_rows
        if mode == "flash":
            pc = self.shown_r[15] or FLASH_BASE + 8
            start = max(FLASH_BASE, (pc & ~3) - 16)
            addrs = [start + 4 * k for k in range(n)]
            title = "Flash（程序）"
        elif mode == "vars":
            addrs = [SRAM_BASE + 4 * k for k in range(n)]
            title = "SRAM 低地址（全局变量）"
        else:
            addrs = [STACK_TOP - 4 - 4 * k for k in range(n)]
            title = "SRAM 高地址（栈，往下长）"
        auto = "自动跟随" if self.mem_mode == "auto" else "手动"
        self.panels.mem_title.setText("内存 · %s  [M 切换，%s]" % (title, auto))
        a_col, v_col, n_col = [], [], []
        for k, a in enumerate(addrs):
            v = self.mem_hidden.get(a, bus.peek(a))
            note = self.names.get(a, "")
            if mode == "stack":
                if a == sp:
                    note = colored("acc", "← SP 指在这里")
                elif a > sp and sp >= SRAM_BASE:
                    note = "栈里存着的数"
                else:
                    note = colored("dim", "（空，还没用到）")
            elif mode == "vars" and not note:
                note = colored("dim", "（没用到）")
            a_col.append(_addr(a))
            v_col.append(hex32(v) if v is not None else "--")
            n_col.append(note or " ")
            if highlight and highlight[0] == a and highlight[1]:
                self.panels.mark(self.panels.mem_bars, k, highlight[1], 1.6)
        for t, s in zip(self.panels.mem_cols, (a_col, v_col, n_col)):
            t.setText("\n".join(s))

    def refresh_alu(self):
        p = self.panels
        b = self.last_alu
        if b is None:
            p.alu_labels.setText("ALU")
            p.alu_bits.setText(colored("dim", "（还没有做过运算）"))
            p.alu_dec.setText("")
            p.alu_flags.setText("")
            return
        sym = {"+": "+", "-": "+", "&": "与", "|": "或", "^": "异或", "&~": "清除",
               "~": "取反", "*": "×", "<<": "左移", ">>": "右移", "pass": "通过"}[b.op]
        if b.op in ("+", "-"):
            labels = ["进位", "A", "B" if b.op == "+" else "~B+1", "结果"]
            rows = [_bits(b.carries, "acc"), _bits(b.a), _bits(b.b_shown), _bits(b.result)]
            decs = [" ", show_value(b.a), show_value(b.b) if b.op == "+" else
                    "-" + show_value(b.b), show_value(b.result)]
        elif b.op in ("<<", ">>", "pass", "~"):
            labels = ["", "输入", "操作", "结果"]
            src = b.b if b.op in ("pass", "~") else b.a
            rows = [" ", _bits(src), colored("dim", "%s %s" % (sym, b.b if b.op in ("<<", ">>")
                                                             else "")), _bits(b.result)]
            decs = [" ", show_value(src), " ", show_value(b.result)]
        else:
            labels = ["", "A", "B（%s）" % sym, "结果"]
            rows = [" ", _bits(b.a), _bits(b.b), _bits(b.result)]
            decs = [" ", show_value(b.a), show_value(b.b), show_value(b.result)]
        p.alu_labels.setText("\n".join(labels))
        p.alu_bits.setText("\n".join(rows))
        p.alu_dec.setText("\n".join(decs))
        if b.set_flags:
            f = b.flags_new
            p.alu_flags.setText("标志位  " + "  ".join(
                colored("hi" if f[k] else "dim", "%s=%d" % (k, f[k])) for k in "NZCV")
                + colored("dim", "    减法 = 加上“取反再加 1”" if b.op == "-" else ""))
        else:
            p.alu_flags.setText(colored("dim", "这次不更新标志位"))

    def refresh_status(self):
        p = self.panels
        cpu = self.machine.cpu
        if self.cur is not None or self.queue:
            done = self.instr_beats - len(self.queue)
            kind = KIND_NAMES.get(self.cur.kind, "") if self.cur else ""
            where = "第 %d/%d 拍 %s" % (done, self.instr_beats, kind)
        else:
            where = "等待下一条指令"
        state = "连续运行中" if self.running else "暂停"
        p.status.setText("已执行 %d 条 · %s · %sx · %s"
                         % (cpu.count, where, _fmt_speed(SPEEDS[self.speed_i]), state))
        text = wrap(self.last_text, p.strip_w / 0.028 - 1).split("\n")
        p.beat_text.setText("\n".join(text[:3]))
        lines = len(text[:3])
        p.beat_text.setPos(self.panels.strip_x0 + 0.02, 0.42)
        bus_z = 0.42 - lines * 0.028 * 1.3 - 0.01
        p.bus_text.setPos(self.panels.strip_x0 + 0.02, bus_z)
        if self.last_bus:
            a, v, rw, what = self.last_bus
            p.bus_text.setText("总线（%s）：%s %s → %s   %s %s   %s" % (
                what, colored("purple", "地址线"), _addr(a), REGION_NAMES[region_of(a)],
                colored("cyan", "数据线"), hex32(v),
                colored("green", "读") if rw == "read" else colored("hi", "写")))
        else:
            p.bus_text.setText(colored("dim", "总线：还没有访问"))
        alu_z = bus_z - 0.026 * 1.35 - 0.005
        for t, x in ((p.alu_labels, p.strip_x0 + 0.02), (p.alu_bits, p.strip_x0 + 0.13),
                     (p.alu_dec, p.strip_x0 + p.strip_w - 0.02)):
            t.setPos(x, alu_z)
        p.alu_flags.setPos(p.strip_x0 + 0.02, alu_z - 4 * 0.026 * 1.36)


def _addr(a):
    return "%04X %04X" % (a >> 16, a & 0xFFFF)


def _bits(v, one="hi"):
    out = []
    for nib in range(7, -1, -1):
        chunk = ""
        for i in range(3, -1, -1):
            bit = v >> (nib * 4 + i) & 1
            chunk += colored(one, "1") if bit else colored("dim", "0")
        out.append(chunk)
    return " ".join(out)


def _alu_summary(b):
    if b.op == "pass":
        return "通过：%s" % show_value(b.result)
    sym = {"+": "+", "-": "-", "&": "&", "|": "|", "^": "^", "&~": "& ~", "~": "~",
           "*": "×", "<<": "<<", ">>": ">>"}[b.op]
    if b.op == "~":
        return "~%s = %s" % (show_value(b.b), show_value(b.result))
    return "%s %s %s = %s" % (show_value(b.a), sym, show_value(b.b), show_value(b.result))


def _fmt_speed(s):
    return ("%g" % s)


def program_menu_text(keys):
    return "   ".join("%d %s" % (k + 1, PROGRAMS[key].title) for k, key in enumerate(keys))


ALL_PROGRAMS = ORDER
