"""第 7 课：UART 串口通信——拆开 UART 外设看它的内部组成。"""

import string

from .. import parts, theme
from ..ui import set_text
from .base import Lesson

Z = 0.25
CELL, CELL_GAP = 0.42, 0.06
A_PIN_X, B_PIN_X = -3.0, 3.0
LINE_Y, BACK_Y, GND_Y = 0.0, -1.2, -2.0
ROW_TOP, ROW_MID = 2.2, 0.0
BIT_TIMES = [0.9, 0.55, 0.32, 0.18]
EMPTY = (0.22, 0.24, 0.3, 1)

INTRO = (
    "UART（通用异步收发器）是 MCU 里的一个外设，专门负责串口通信。"
    "“串行”指数据一位接一位地走同一根线；“异步”指双方没有共用的时钟线，"
    "全靠事先约定好的速度——波特率。\n\n"
    "两块 MCU 之间只要三根线：A 的 TX（发送）接 B 的 RX（接收），"
    "B 的 TX 接 A 的 RX，再加一根 GND（地线，0V 的共同参考）。\n\n"
    "UART 外设内部主要由这几部分组成（画面里两块芯片上的方块）：\n"
    "· TDR 发送数据寄存器：CPU 把要发的字节写到这里\n"
    "· 发送移位寄存器：把字节从 TDR 整个搬进来，然后每个节拍往右挤出一位到 TX 引脚\n"
    "· 波特率发生器：把系统时钟分频，产生“每一位”的节拍\n"
    "· 接收移位寄存器：每个节拍从 RX 引脚收进一位，攒满 8 位\n"
    "· RDR 接收数据寄存器：收满的字节放在这里，等 CPU 来取\n"
    "· 状态寄存器：TXE=1 表示 TDR 空了可以写下一个；RXNE=1 表示 RDR 里有新数据\n\n"
    "一帧数据：空闲时线路是高电平 1 → 起始位 0 → 8 个数据位（低位 bit0 先发）"
    " → 停止位 1。")


class UARTLesson(Lesson):
    title = "UART 串口通信"
    summary = "拆开串口外设，看一个字节怎么发出去"
    hints = ("键盘打字（字母/数字） 发送该字符   空格 发送 \"Hi\"\n"
             "上下方向键 调整速度")
    camera = (38, 0, -52, (0.3, 0.3, 0.5))
    location = ["uart", "cpu", "clock", "bus", "pins"]
    location_text = (
        "UART 外设（芯片下排青色那块）。TDR、RDR、移位寄存器、状态寄存器、"
        "波特率发生器都在 UART 外设内部；TX、RX 是借给 UART 使用的两个 GPIO 引脚。"
        "CPU 通过总线读写 TDR / RDR，就像读写一个普通变量一样"
        "（STM32F103 的 USART1 数据寄存器地址是 0x4001 3804）。")
    terms = ["UART", "串行", "异步", "TX", "RX", "GND", "波特率", "帧", "起始位",
             "停止位", "ASCII", "移位寄存器", "TDR", "RDR", "状态寄存器", "标志位",
             "TXE", "RXNE", "波特率发生器"]

    def setup(self):
        self.queue = []
        self.speed_i = 1
        self.received = ""
        self.state = "idle"
        self.wait_t = 0.0
        self.wait_next = None
        self.train = None
        self.ch = None
        self.bits = None
        self.step_text = "等待发送……（按键盘上的字母试试）"
        self.rx_bits = []

        self.box((22, 10, 0.2), (0, 0.3, -0.1), theme.PCB)
        self._build_mcu_a()
        self._build_mcu_b()
        # 三根线
        self.tx_wire = self.wire([(A_PIN_X, LINE_Y, Z), (B_PIN_X, LINE_Y, Z)],
                                 theme.HIGH, 6)
        self.wire([(A_PIN_X, BACK_Y, Z), (B_PIN_X, BACK_Y, Z)], theme.WIRE_IDLE, 3)
        self.wire([(A_PIN_X, GND_Y, Z), (B_PIN_X, GND_Y, Z)], (0.3, 0.3, 0.3, 1), 3)
        self.label("A的TX → B的RX", (0, LINE_Y + 0.45, Z), 0.28, theme.TEXT_DIM)
        self.label("A的RX ← B的TX（这次没用）", (0, BACK_Y + 0.4, Z), 0.24,
                   theme.TEXT_DIM)
        self.label("GND 地线", (0, GND_Y + 0.4, Z), 0.24, theme.TEXT_DIM)

        for ch in string.ascii_lowercase + string.digits:
            self.accept(ch, self.send, [ch])
        for ch in string.ascii_lowercase:
            self.accept("shift-" + ch, self.send, [ch.upper()])
        self.accept("space", self.send, ["Hi"])
        self.accept_keys(["arrow_up", "="], self.change_speed, [1])
        self.accept_keys(["arrow_down", "-"], self.change_speed, [-1])
        self.refresh()

    # ------------------------------------------------------------ 场景
    def _plate(self, x0, x1, title):
        self.box((x1 - x0, 7.4, 0.15), ((x0 + x1) / 2, 0.3, 0.08), (0.13, 0.14, 0.18, 1))
        self.label(title, ((x0 + x1) / 2, 4.4, 0.4), 0.4)
        # 表示 UART 外设范围的框
        ux0, ux1 = (x0 + 0.3, x1 - 0.3)
        frame = self.box((ux1 - ux0, 6.2, 0.05), ((ux0 + ux1) / 2, 0.1, 0.18),
                         theme.scale(theme.UART, 0.45))
        frame.setLightOff(1)
        self.label("UART 外设", ((ux0 + ux1) / 2, -2.8, 0.3), 0.3, theme.UART)

    def _cells(self, cx, y, name, sub=""):
        cells = []
        n = 8
        total = n * CELL + (n - 1) * CELL_GAP
        x = cx - total / 2 + CELL / 2
        for i in range(n):
            box = self.box((CELL, CELL, 0.25), (x, y, 0.35), EMPTY)
            lbl = self.label("", (x, y, 0.85), 0.3)
            cells.append((box, lbl))
            x += CELL + CELL_GAP
        self.label(name, (cx, y + 0.55, 0.4), 0.26, theme.TEXT)
        if sub:
            self.label(sub, (cx, y - 0.5, 0.3), 0.2, theme.TEXT_DIM)
        return cells

    def _flag(self, x, y, name):
        box = self.box((0.6, 0.45, 0.25), (x, y, 0.35), EMPTY)
        lbl = self.label("0", (x, y, 0.85), 0.3)
        self.label(name, (x, y - 0.45, 0.3), 0.22, theme.TEXT_DIM)
        return box, lbl

    def _build_mcu_a(self):
        self._plate(-10.2, -3.2, "MCU A（发送方）")
        self.cpu_a = self.box((1.6, 1.1, 0.5), (-8.9, ROW_TOP, 0.4), theme.CPU)
        self.label("CPU", (-8.9, ROW_TOP, 1.0), 0.3)
        self.tdr = self._cells(-5.5, ROW_TOP, "TDR 发送数据寄存器", "b7 ……… b0")
        self.tsr = self._cells(-5.5, ROW_MID, "发送移位寄存器", "每个节拍往右挤出一位 →")
        self.wire([(-3.55, ROW_MID, Z + 0.1), (A_PIN_X, LINE_Y, Z)], theme.UART, 3)
        self.baud_a = self.box((1.6, 1.0, 0.5), (-8.9, -0.6, 0.4), theme.CLOCK)
        self.label("波特率\n发生器", (-8.9, -0.6, 1.25), 0.24)
        self.flag_txe = self._flag(-6.6, -1.9, "TXE 发送寄存器空")
        self.box((0.3, 0.3, 0.3), (A_PIN_X, LINE_Y, Z), theme.PIN)
        self.label("TX 引脚", (A_PIN_X - 0.2, LINE_Y - 0.45, 0.3), 0.22,
                   theme.TEXT_DIM, align="right")
        self.set_flag(self.flag_txe, 1)

    def _build_mcu_b(self):
        self._plate(3.2, 10.2, "MCU B（接收方）")
        self.cpu_b = self.box((1.6, 1.1, 0.5), (8.9, ROW_TOP, 0.4), theme.CPU)
        self.label("CPU", (8.9, ROW_TOP, 1.0), 0.3)
        self.rdr = self._cells(5.5, ROW_TOP, "RDR 接收数据寄存器", "b7 ……… b0")
        self.rsr = self._cells(5.5, ROW_MID, "接收移位寄存器", "→ 每个节拍从左边收进一位")
        self.wire([(B_PIN_X, LINE_Y, Z), (3.55, ROW_MID, Z + 0.1)], theme.UART, 3)
        self.baud_b = self.box((1.6, 1.0, 0.5), (8.9, -0.6, 0.4), theme.CLOCK)
        self.label("波特率\n发生器", (8.9, -0.6, 1.25), 0.24)
        self.flag_rxne = self._flag(6.6, -1.9, "RXNE 收到新数据")
        self.box((0.3, 0.3, 0.3), (B_PIN_X, LINE_Y, Z), theme.PIN)
        self.label("RX 引脚", (B_PIN_X + 0.2, LINE_Y - 0.45, 0.3), 0.22,
                   theme.TEXT_DIM, align="left")
        self.rx_text = self.label("", (6.7, 5.3, 0.5), 0.36, theme.ACCENT)
        self.tx_text = self.label("", (-6.7, 5.3, 0.5), 0.32, theme.TEXT)

    # ------------------------------------------------------------ 显示工具
    def set_cells(self, cells, values):
        """values: 从左到右每格的值（0/1/None）。"""
        for (box, lbl), v in zip(cells, values):
            if v is None:
                box.setColor(*EMPTY, 1)
                set_text(lbl, "")
            else:
                box.setColor(*(theme.HIGH if v else theme.LOW), 1)
                set_text(lbl, str(v))

    def set_flag(self, flag, v):
        box, lbl = flag
        box.setColor(*(theme.ACCENT if v else EMPTY), 1)
        set_text(lbl, str(v))

    @staticmethod
    def msb_first(code):
        return [code >> (7 - i) & 1 for i in range(8)]

    def refresh(self):
        set_text(self.rx_text, "B 收到：%s" % (self.received or "（空）"))
        set_text(self.tx_text, "A 待发送：%s" % ("".join(self.queue) or "（空）"))
        body = INTRO + "\n\n【现在】" + self.step_text
        if self.ch:
            code = ord(self.ch)
            b = format(code, "08b")
            body += ("\n\n正在发送 '%s'：ASCII 码 %d = 0x%02X = 二进制 %s %s\n"
                     "线上的顺序：0（起始） %s（低位先发） 1（停止）"
                     % (self.ch, code, code, b[:4], b[4:], " ".join(b[::-1])))
        self.set_body(body)

    def say(self, text):
        self.step_text = text
        self.refresh()

    def wait(self, seconds, then):
        self.wait_t = seconds
        self.wait_next = then

    # ------------------------------------------------------------ 输入
    def send(self, text):
        if len(self.queue) < 20:
            self.queue.extend(text)
        self.refresh()

    def change_speed(self, d):
        self.speed_i = max(0, min(len(BIT_TIMES) - 1, self.speed_i + d))

    # ------------------------------------------------------------ 发送流程
    def start_char(self, ch):
        self.state = "busy"
        self.ch = ch
        self.bits = self.msb_first(ord(ch))
        self.say("① CPU 把 '%s'（0x%02X）通过总线写进 TDR。写入后 TXE 变成 0，"
                 "表示“TDR 里有数据，还没搬走”。" % (ch, ord(ch)))
        self.movers.append(parts.Packet(
            self.root, [(-8.9, ROW_TOP, 0.9), (-5.5, ROW_TOP, 0.9)], theme.CPU,
            speed=5.0, size=0.35, label="'%s'" % ch, on_done=self.tdr_written))

    def tdr_written(self):
        self.set_cells(self.tdr, self.bits)
        self.set_flag(self.flag_txe, 0)
        self.wait(0.9, self.load_shift)

    def load_shift(self):
        self.set_cells(self.tdr, [None] * 8)
        self.set_cells(self.tsr, self.bits)
        self.set_flag(self.flag_txe, 1)
        self.say("② 发送移位寄存器空着，UART 自动把 8 位一次性从 TDR 搬进来。"
                 "TDR 又空了，TXE 变回 1——CPU 此时就可以写下一个字节，不用等它发完。")
        self.wait(1.2, self.start_frame)

    def start_frame(self):
        code = ord(self.ch)
        frame = [0] + [code >> i & 1 for i in range(8)] + [1]
        labels = ["起"] + [str(b) for b in frame[1:9]] + ["停"]
        T = BIT_TIMES[self.speed_i]
        self.rx_bits = []
        self.set_cells(self.rsr, [None] * 8)
        self.say("③ 波特率发生器开始打节拍：第一拍先把 TX 拉低，发出起始位 0；"
                 "之后每一拍，移位寄存器把最右边的一位（先是 bit0）挤到 TX 引脚上，"
                 "其余的位往右挪一格。")
        self.train = parts.BitTrain(
            self.root, frame, (A_PIN_X, LINE_Y, 0.6), (B_PIN_X, LINE_Y, 0.6),
            T, 0.75, labels, on_bit=self.bit_arrived, on_done=self.frame_done)
        self.movers.append(self.train)

    def bit_arrived(self, i):
        if i == 0:
            self.say("④ B 的 RX 引脚看到电平从 1 变成 0：起始位！"
                     "B 的波特率发生器按同样的节拍开始采样。")
        elif i <= 8:
            b = ord(self.ch) >> (i - 1) & 1
            self.rx_bits.insert(0, b)       # 从左边挤进来，先到的被推到右边
            self.set_cells(self.rsr, self.rx_bits + [None] * (8 - len(self.rx_bits)))
            self.say("⑤ B 收到 bit%d = %d，从左边挤进接收移位寄存器。" % (i - 1, b))
        else:
            self.say("⑥ 收到停止位 1，8 位攒齐了。")

    def frame_done(self):
        self.train = None
        self.set_cells(self.tsr, [None] * 8)
        self.set_cells(self.rdr, self.rx_bits)
        self.set_cells(self.rsr, [None] * 8)
        self.set_flag(self.flag_rxne, 1)
        self.say("⑦ 接收移位寄存器把整个字节搬进 RDR，RXNE 变成 1，"
                 "告诉 CPU“有新数据”（如果开了中断，这时就会触发 UART 接收中断）。")
        self.wait(1.2, self.cpu_read)

    def cpu_read(self):
        self.movers.append(parts.Packet(
            self.root, [(5.5, ROW_TOP, 0.9), (8.9, ROW_TOP, 0.9)], theme.CPU,
            speed=5.0, size=0.35, label="'%s'" % self.ch, on_done=self.char_done))

    def char_done(self):
        self.received = (self.received + self.ch)[-16:]
        self.set_cells(self.rdr, [None] * 8)
        self.set_flag(self.flag_rxne, 0)
        self.say("⑧ CPU 读走 RDR 里的 '%s'，RXNE 自动清 0。一个字节传输完成！" % self.ch)
        self.ch = None
        self.state = "idle"
        self.wait(0.6, None)

    # ------------------------------------------------------------ 每帧
    def update(self, dt):
        if self.wait_t > 0:
            self.wait_t -= dt
            if self.wait_t <= 0 and self.wait_next:
                nxt, self.wait_next = self.wait_next, None
                nxt()
        if self.state == "idle" and self.wait_t <= 0 and self.queue:
            self.start_char(self.queue.pop(0))
            self.refresh()

        level = 1
        tick = False
        if self.train is not None and not self.train.done:
            T = self.train.bit_time
            idx = self.train.current_index()
            frame = [0] + [ord(self.ch) >> i & 1 for i in range(8)] + [1]
            level = frame[idx] if idx < len(frame) else 1
            # 移位寄存器：第 k 个数据位送出时，已经往右挪了 k 次
            shifts = max(0, min(8, idx))
            shown = [None] * shifts + self.bits[:8 - shifts]
            self.set_cells(self.tsr, shown)
            tick = (self.train.t % T) < T * 0.3
        c = theme.HIGH if level else theme.LOW
        self.tx_wire.setColor(c[0], c[1], c[2], 1, 1)
        k = 2.0 if tick else 1.0
        self.baud_a.setColorScale(k, k, k, 1)
        self.baud_b.setColorScale(k, k, k, 1)
