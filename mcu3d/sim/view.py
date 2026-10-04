"""芯片内部模拟器的画面。

中间是 3D 芯片：CPU（寄存器组、标志位、控制单元、ALU）、三组总线线路、Flash、SRAM、外设区。
右边是 2D 数据面板：C 代码 / 汇编 / 机器码、寄存器表、内存表。
下方是“这一拍”说明、总线上的信号，以及 ALU 一位一位的计算过程。

CPU 每执行一条指令会产生若干“拍”（见 machine.Beat），这里按拍播放：
on_start 时放动画、亮模块，on_end 时把新值写进面板。
"""

from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode

from .. import parts, shapes, theme
from ..ui import colored, set_text, text3d, wrap
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

ADDR_COLOR = (0.75, 0.5, 1.0, 1)
DATA_COLOR = (0.3, 0.85, 1.0, 1)
CTRL_IDLE = (0.45, 0.47, 0.52, 1)
READ_COLOR = (0.35, 0.9, 0.45, 1)
WRITE_COLOR = (1.0, 0.5, 0.2, 1)
REG_COLOR = (0.55, 0.22, 0.24, 1)

# 右侧数据面板（aspect2d 单位，相对右上角）
RW = 1.24
RX = -RW - 0.02
SCALE = 0.027

# 3D 布局
TRUNK_X = {"addr": -0.45, "data": 0.0, "ctrl": 0.45}
TRUNK_Y0, TRUNK_Y1 = -1.3, 5.2
BRANCH_Y = 2.4
TARGET_EDGE = {"flash": (-1.0, BRANCH_Y), "sram": (1.0, BRANCH_Y), "periph": (None, 5.3)}

# 点击 3D 模块时的介绍
MODULES = {
    "regs": ("寄存器组",
             "CPU 内部的 16 个 32 位寄存器，是 CPU 手边的“草稿格子”，读写只要一拍。\n\n"
             "· R0~R12：通用寄存器，放正在计算的数。函数的参数和返回值也用 R0~R3\n"
             "· SP（R13）：栈指针，指向 SRAM 里栈的最上面一格\n"
             "· LR（R14）：链接寄存器，调用函数时记住“回到哪里”\n"
             "· PC（R15）：程序计数器，记着下一条指令在 Flash 的哪个地址\n\n"
             "它们没有地址，只有 CPU 自己能直接用。CPU 做任何计算，都要先把数放进寄存器。"),
    "flags": ("标志位 NZCV",
              "程序状态寄存器（xPSR）里的 4 个位，记录上一次运算结果的特点：\n\n"
              "· N（Negative）：结果是负数（最高位是 1）\n"
              "· Z（Zero）：结果是 0\n"
              "· C（Carry）：加法有进位，或减法没有借位\n"
              "· V（oVerflow）：有符号数溢出，比如正数 + 正数变成了负数\n\n"
              "条件跳转（BEQ、BLE……）就是看这几个位决定跳不跳，C 语言的 if、while 全靠它们。"),
    "decoder": ("控制单元（指令译码器）",
                "CPU 的“指挥”。取回来的机器码先送到这里，它看懂这串 0 和 1 是哪条指令、"
                "要用哪几个寄存器，然后发出控制信号：让寄存器组送出数据、让 ALU 做加法还是与运算、"
                "让总线去读还是写。"),
    "alu": ("ALU 算术逻辑单元",
            "CPU 里真正做计算的电路：加、减、与、或、异或、移位、比较……\n\n"
            "它一次处理 32 位，每一位都是一个小加法器，低位的进位传给高位。"
            "算完顺便把结果的特点记进标志位 NZCV。"),
    "flash": ("Flash 程序存储器（0x0800 0000 起）",
              "存放程序的地方，断电不丢。最前面是向量表：第 0 个字是栈顶地址，第 1 个字是复位后"
              "第一条指令的地址；后面是一条条机器码，再后面是“文字池”（程序用到的常数，比如变量的地址）。\n\n"
              "CPU 每执行一条指令都要先从这里“取指”。运行时它是只读的。"),
    "sram": ("SRAM 数据存储器（0x2000 0000 起，20KB）",
             "存放运行时数据，读写都快，断电就丢。\n\n"
             "· 低地址那头：全局变量，一个 int 占 4 字节，一个挨一个\n"
             "· 高地址那头（0x2000 5000 往下）：栈，函数调用时保存返回地址和寄存器\n\n"
             "CPU 不能直接在这里做计算，要先读进寄存器，算完再写回来。"),
    "periph": ("外设区（0x4000 0000 起）",
               "GPIO、定时器、UART、ADC 等外设的寄存器都在这段地址里。"
               "CPU 读写它们和读写 SRAM 一模一样，只是写进去的数会变成引脚电平、"
               "定时时间、串口数据……第 8 课起会把它们接进模拟器。"),
    "bus_addr": ("地址线",
                 "32 根线，CPU 在上面放出要访问的地址（比如 0x2000 0000），"
                 "总线根据地址找到对应的模块：0x08… 是 Flash，0x20… 是 SRAM，0x40… 是外设。"),
    "bus_data": ("数据线",
                 "32 根线，传送真正的数据。读的时候由存储器把数放上来送给 CPU；"
                 "写的时候由 CPU 把数放上去送给存储器。"),
    "bus_ctrl": ("读 / 写控制线",
                 "告诉被访问的模块这次是“读”还是“写”。画面上绿色表示读，橙色表示写。"),
}


class Chip3D:
    """3D 芯片模型。所有节点挂在 lesson.root 下，课程销毁时一起消失。"""

    def __init__(self, lesson):
        self.L = L = lesson
        self.root = L.root.attachNewNode("sim-chip")
        L.box((9.6, 15.4, 0.2), (0, -0.4, -0.12), theme.DIE, parent=self.root)

        # ---- CPU ----
        L.box((8.6, 6.0, 0.12), (0, -4.6, 0.02), (0.28, 0.12, 0.13, 1), parent=self.root)
        L.label("CPU 内核", (-4.1, -1.75, 0.3), 0.55, theme.CPU, parent=self.root,
                align="left")
        self.reg_cubes = []
        self.reg_base = []
        for i in range(16):
            col, row = i % 4, i // 4
            pos = (-3.45 + col * 0.82, -2.6 - row * 0.82, 0.32)
            cube = L.box((0.64, 0.64, 0.4), pos, REG_COLOR, parent=self.root, pick="regs")
            text3d(REG_NAMES[i], cube, (0, 0, 0.5), 0.36, theme.TEXT)
            self.reg_cubes.append(cube)
            self.reg_base.append(pos)
        L.label("寄存器组", (-2.22, -6.05, 0.3), 0.42, theme.TEXT_DIM, parent=self.root)
        self.flag_cubes = {}
        for k, name in enumerate("NZCV"):
            cube = L.box((0.5, 0.5, 0.3), (-3.45 + k * 0.82, -6.75, 0.26), (0.2, 0.2, 0.24, 1),
                         parent=self.root, pick="flags")
            text3d(name, cube, (0, 0, 0.4), 0.38, theme.TEXT)
            self.flag_cubes[name] = cube
        L.label("标志位", (-0.6, -6.85, 0.3), 0.42, theme.TEXT_DIM, parent=self.root,
                align="left")

        self.decoder = L.box((3.4, 1.5, 0.5), (2.2, -2.9, 0.35), (0.42, 0.3, 0.5, 1),
                             parent=self.root, pick="decoder")
        L.label("控制单元（译码器）", (2.2, -1.95, 0.7), 0.4, theme.TEXT_DIM, parent=self.root)
        self.decoder_text = L.label("", (2.2, -2.9, 0.95), 0.4, theme.ACCENT,
                                    parent=self.root)
        self.alu = L.box((3.4, 2.0, 0.6), (2.2, -5.4, 0.4), (0.55, 0.38, 0.18, 1),
                         parent=self.root, pick="alu")
        L.label("ALU 运算器", (2.2, -4.2, 0.8), 0.42, theme.TEXT_DIM, parent=self.root)
        self.alu_text = L.label("", (2.2, -5.4, 1.1), 0.45, theme.ACCENT, parent=self.root)
        # CPU 内部的数据通路：寄存器组 <-> ALU，控制单元 -> ALU
        L.wire([(-0.7, -4.0, 0.25), (0.5, -5.0, 0.25)], (0.6, 0.6, 0.65, 1), 2,
               parent=self.root)
        L.wire([(0.5, -5.8, 0.25), (-0.7, -4.6, 0.25)], (0.6, 0.6, 0.65, 1), 2,
               parent=self.root)
        L.wire([(2.2, -3.65, 0.25), (2.2, -4.4, 0.25)], (0.6, 0.6, 0.65, 1), 2,
               parent=self.root)

        # ---- 总线 ----
        self.trunks = {}
        colors = {"addr": ADDR_COLOR, "data": DATA_COLOR, "ctrl": CTRL_IDLE}
        for key, x in TRUNK_X.items():
            t = shapes.flat_trace((x, TRUNK_Y0, 0.06), (x, TRUNK_Y1, 0.06), 0.16, 0.06,
                                  colors[key])
            t.reparentTo(self.root)
            t.setLightOff(1)
            L.make_pickable(t, "bus_" + key)
            self.trunks[key] = t
        for sx in (-1, 1):
            for key, x in TRUNK_X.items():
                y = BRANCH_Y + {"addr": 0.3, "data": 0.0, "ctrl": -0.3}[key]
                b = shapes.flat_trace((x, y, 0.05), (sx * 1.0, y, 0.05), 0.1, 0.05,
                                      theme.scale(colors[key], 0.7))
                b.reparentTo(self.root)
                b.setLightOff(1)
        L.label("地址线", (-0.6, -0.6, 0.3), 0.36, (0.8, 0.6, 1, 1), parent=self.root,
                align="right")
        L.label("读/写线", (0.6, -0.6, 0.3), 0.36, (0.75, 0.77, 0.8, 1), parent=self.root,
                align="left")
        L.label("数据线", (0.0, 0.6, 0.45), 0.34, (0.5, 0.9, 1, 1), parent=self.root)
        L.label("系统总线", (0.0, 4.6, 0.5), 0.4, theme.ACCENT, parent=self.root)

        # ---- 存储器与外设 ----
        self.blocks = {
            "flash": L.box((2.8, 2.8, 0.6), (-2.6, BRANCH_Y, 0.35), theme.FLASH,
                           parent=self.root, pick="flash"),
            "sram": L.box((2.8, 2.8, 0.6), (2.6, BRANCH_Y, 0.35), theme.SRAM,
                          parent=self.root, pick="sram"),
            "periph": L.box((7.6, 1.6, 0.5), (0, 6.1, 0.3), (0.45, 0.4, 0.3, 1),
                            parent=self.root, pick="periph"),
        }
        L.label("Flash\n0x0800 0000", (-2.6, BRANCH_Y, 1.0), 0.42, parent=self.root)
        L.label("SRAM\n0x2000 0000", (2.6, BRANCH_Y, 1.0), 0.42, parent=self.root)
        L.label("外设区 0x4000 0000\n（第 8 课起接入）", (0, 6.1, 0.9),
                0.4, theme.TEXT_DIM, parent=self.root)

        self.glow = {}       # 节点 -> 剩余发光时间
        self.popups = []

    # ---- 动画辅助 ----
    def flash_node(self, np, t=0.8, color=None):
        self.glow[np] = [t, color]

    def set_ctrl(self, mode):
        self.trunks["ctrl"].setColor({"read": READ_COLOR, "write": WRITE_COLOR}.get(
            mode, CTRL_IDLE))

    def set_flags(self, flags):
        for k, cube in self.flag_cubes.items():
            cube.setColor(theme.HIGH if flags[k] else (0.2, 0.2, 0.24, 1))

    def popup(self, text, pos, color=theme.ACCENT, life=1.2):
        np = text3d(text, self.root, pos, 0.45, color)
        self.popups.append([np, life])

    def path(self, line, target):
        """从 CPU 出发，沿某根总线走到目标模块的路径。"""
        x = TRUNK_X[line]
        ex, ey = TARGET_EDGE[target]
        if target == "periph":
            return [(x, TRUNK_Y0, 0.4), (x, ey, 0.4)]
        dy = {"addr": 0.3, "data": 0.0, "ctrl": -0.3}[line]
        return [(x, TRUNK_Y0, 0.4), (x, ey + dy, 0.4), (ex, ey + dy, 0.4)]

    def update(self, dt, time):
        for np, item in list(self.glow.items()):
            item[0] -= dt
            if item[0] <= 0 or np.isEmpty():
                if not np.isEmpty():
                    np.clearColorScale()
                del self.glow[np]
                continue
            k = 1.3 + 0.6 * parts.pulse(time, 10)
            c = item[1]
            if c:
                np.setColorScale(c[0] * k, c[1] * k, c[2] * k, 1)
            else:
                np.setColorScale(k, k, k, 1)
        for item in list(self.popups):
            item[1] -= dt
            item[0].setZ(item[0].getZ() + dt * 0.4)
            if item[1] <= 0:
                item[0].removeNode()
                self.popups.remove(item)


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
    """模拟器：一台 Machine + 3D 芯片 + 2D 面板 + 播放控制。

    lesson 需要提供 root、app、box/label/wire/make_pickable（Lesson 基类都有）。
    """

    def __init__(self, lesson, program="inc", on_beat=None):
        self.lesson = lesson
        self.app = lesson.app
        self.chip = Chip3D(lesson)
        self.panels = Panels(self.app)
        self.on_beat = on_beat
        self.speed_i = 2
        self.running = False
        self.mem_mode = "auto"
        self.mem_focus = "flash"
        self.load(program)

    def destroy(self):
        self.lesson.clear_movers()
        self.panels.destroy()

    # ------------------------------------------------------------ 程序
    def load(self, key):
        self.program = PROGRAMS[key]
        self.machine = Machine(self.program)
        self._build_code_rows()
        self.reset()

    def reset(self):
        self.lesson.clear_movers()
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
        self.last_text = ("按空格执行一条指令，按 T 只走一拍。第一步是“复位”："
                          "CPU 先从向量表读出 SP 和 PC。")
        self.running = False
        self.single = False
        self.chip.set_flags(self.shown_flags)
        self.chip.set_ctrl(None)
        set_text(self.chip.decoder_text, "")
        set_text(self.chip.alu_text, "")
        self.refresh_all()

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
        self.lesson.clear_movers()
        if self.cur is not None:
            self._end_beat()
        while self.queue:
            b = self.queue.pop(0)
            self._begin_beat(b, animate=False)
            self._end_beat()
        self._commit_instruction()

    def _commit_instruction(self):
        cpu = self.machine.cpu
        self.shown_r = list(cpu.r)
        self.shown_flags = dict(cpu.flags)
        self.mem_hidden = {}
        self.instr_addr = None
        self.chip.set_ctrl(None)
        self.chip.set_flags(self.shown_flags)
        self.refresh_all()

    def _begin_beat(self, b, animate=True):
        self.cur = b
        self.cur_t = 0.0
        self.cur_len = BEAT_TIME.get(b.kind, 0.8)
        self.last_text = b.text
        ch = self.chip
        speed = SPEEDS[self.speed_i]
        dur = self.cur_len / speed
        show = animate and speed <= 4
        k = b.kind
        if k == "fetch":
            self.mem_focus = "flash"
            self.last_bus = (b.addr, b.value, "read", "取指")
            ch.set_ctrl("read")
            ch.flash_node(ch.blocks["flash"], dur)
            ch.flash_node(ch.reg_cubes[15], dur * 0.5)
            if show:
                self._packets("flash", b.addr, b.value, dur, read=True,
                              digits=8 if b.size == 4 else 4)
            self.refresh_code()
            self.refresh_mem(highlight=(b.addr & ~3, (0.2, 0.45, 0.9)))
        elif k == "decode":
            ch.flash_node(ch.decoder, dur)
            set_text(ch.decoder_text, b.asm)
        elif k == "read_reg":
            for r in b.regs:
                ch.flash_node(ch.reg_cubes[r], dur, (0.5, 0.75, 1.0))
                self.panels.mark(self.panels.reg_bars, r, (0.2, 0.45, 0.9), dur + 0.4)
        elif k == "alu":
            self.last_alu = b
            ch.flash_node(ch.alu, dur)
            set_text(ch.alu_text, _alu_summary(b))
            self.refresh_alu()
        elif k in ("mem_read", "mem_write"):
            region = region_of(b.addr) or "periph"
            read = k == "mem_read"
            self._focus_mem(b.addr)
            self.last_bus = (b.addr, b.value, "read" if read else "write",
                             "读数据" if read else "写数据")
            ch.set_ctrl("read" if read else "write")
            ch.flash_node(ch.blocks[region], dur)
            if show:
                self._packets(region, b.addr, b.value, dur, read=read,
                              digits=2 if b.size == 1 else 8)
            self.refresh_mem(highlight=(b.addr & ~3, (0.2, 0.45, 0.9) if read else None))
        elif k == "write_reg":
            self.shown_r[b.reg] = b.new
            ch.flash_node(ch.reg_cubes[b.reg], dur, (1.0, 0.6, 0.25))
            self.panels.mark(self.panels.reg_bars, b.reg, (0.85, 0.45, 0.1), dur + 0.6)
            if show:
                x, y, z = ch.reg_base[b.reg]
                ch.popup(show_value(b.new), (x, y, z + 0.9), life=dur + 0.4)
            self.refresh_regs()
        elif k == "branch":
            if b.taken:
                ch.flash_node(ch.reg_cubes[15], dur, (1.0, 0.6, 0.25))
            ch.flash_node(ch.flag_cubes["N"], dur * 0.5)
        elif k == "fault":
            self.fault = b.text
            self.running = False
        if self.on_beat:
            self.on_beat(b)
        self.refresh_status()

    def _end_beat(self):
        b = self.cur
        self.cur = None
        if b is None:
            return
        k = b.kind
        if k == "fetch":
            self.shown_r[15] = b.next_pc
            self.refresh_regs()
        elif k == "alu":
            if b.set_flags:
                self.shown_flags = dict(b.flags_new)
                self.chip.set_flags(self.shown_flags)
                self.refresh_regs()
        elif k == "mem_write":
            self.mem_hidden.pop(b.addr & ~3, None)
            self.refresh_mem(highlight=(b.addr & ~3, (0.85, 0.45, 0.1)))
        elif k == "branch":
            if b.taken:
                self.shown_r[15] = b.target
                self.panels.mark(self.panels.reg_bars, 15, (0.85, 0.45, 0.1), 1.0)
                self.refresh_regs()

    def _packets(self, region, addr, value, dur, read, digits):
        ch = self.chip
        L = self.lesson
        half = dur * 0.45
        apath = ch.path("addr", region)
        dpath = ch.path("data", region)
        L.movers.append(parts.Packet(L.root, apath, ADDR_COLOR, _plen(apath) / half, 0.4,
                                     label=_short_addr(addr), label_scale=0.5))
        vtext = ("%0" + str(digits) + "X") % value
        if read:
            back = list(reversed(dpath))

            def later(back=back, vtext=vtext):
                L.movers.append(parts.Packet(L.root, back, DATA_COLOR, _plen(back) / half,
                                             0.4, label=vtext, label_scale=0.5))
            L.movers.append(_Delay(half, later))
        else:
            L.movers.append(parts.Packet(L.root, dpath, DATA_COLOR, _plen(dpath) / half,
                                         0.4, label=vtext, label_scale=0.5))

    def _focus_mem(self, addr):
        reg = region_of(addr)
        if reg == "flash":
            self.mem_focus = "flash"
        elif reg == "sram":
            self.mem_focus = "stack" if addr >= self.shown_r[13] - 16 and addr >= \
                STACK_TOP - 0x400 else "vars"

    def update(self, dt):
        self.chip.update(dt, self.lesson.time)
        self.panels.update(dt)
        if self.cur is not None:
            self.cur_t += dt * SPEEDS[self.speed_i]
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


class _Delay:
    """过一会儿再执行某件事（借用 lesson.movers 的更新机制）。"""

    def __init__(self, t, func):
        self.t = t
        self.func = func
        self.done = False

    def update(self, dt):
        self.t -= dt
        if self.t <= 0 and not self.done:
            self.done = True
            self.func()

    def destroy(self):
        self.done = True


def _plen(path):
    total = 0.0
    for a, b in zip(path, path[1:]):
        total += sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5
    return max(total, 0.01)


def _addr(a):
    return "%04X %04X" % (a >> 16, a & 0xFFFF)


def _short_addr(a):
    return "%08X" % a


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
