"""第 7 课：UART 串口通信。"""

import string

from .. import parts, theme
from ..ui import set_text
from .base import Lesson

A_X, B_X = -6.5, 6.5
WIRE_X0, WIRE_X1 = -4.3, 4.3
TX_Y, RX_Y, GND_Y = 0.6, -0.6, -1.6
SPACING = 0.9
BIT_TIMES = [0.9, 0.55, 0.3, 0.15]

INTRO = ("UART（串口）是最常用的通信方式：两个设备只需要 TX（发送）、RX（接收）"
         "和 GND（地线）三根线。A 的 TX 接 B 的 RX，B 的 TX 接 A 的 RX。\n\n"
         "“串行”的意思是：数据一位一位地排队，从同一根线上依次送过去。\n\n"
         "一帧数据的格式：\n"
         "· 空闲时线路保持高电平 1\n"
         "· 起始位：先拉低成 0，告诉对方“我要开始发了”\n"
         "· 8 个数据位：从最低位 bit0 开始发\n"
         "· 停止位：回到高电平 1，表示这个字节发完了\n\n"
         "双方必须事先约定同样的速度，叫“波特率”，例如 9600 表示每秒 9600 位。"
         "这里放慢了几千倍，方便你看清楚。\n\n"
         "字母在电脑里是用数字表示的（ASCII 码），例如 'A' = 65。")


class UARTLesson(Lesson):
    title = "UART 串口通信"
    summary = "一位一位地“发短信”"
    hints = "键盘打字（字母/数字） 发送该字符   空格 发送 \"Hi\"   上下方向键 调整速度"
    camera = (33, 0, -38, (0.8, -0.5, 1.0))

    def setup(self):
        self.queue = []
        self.frame = None
        self.gap = 0.0
        self.speed_i = 1
        self.rx_bits = [None] * 8
        self.received = ""
        self.rx_status = "等待数据……"

        self.box((20, 7, 0.2), (0, -0.3, -0.1), theme.PCB)
        self.chip_a = parts.Chip(self.root, size=3.5, pos=(A_X, 0, 0), label="A")
        self.chip_b = parts.Chip(self.root, size=3.5, pos=(B_X, 0, 0), label="B")
        self.label("发送方 MCU A", (A_X, 2.9, 0.4), 0.4)
        self.label("接收方 MCU B", (B_X, 2.9, 0.4), 0.4)

        z = 0.2
        self.tx_wire = self.wire([(WIRE_X0, TX_Y, z), (WIRE_X1, TX_Y, z)],
                                 theme.HIGH, 5)
        self.wire([(WIRE_X0, RX_Y, z), (WIRE_X1, RX_Y, z)], theme.WIRE_IDLE, 3)
        self.wire([(WIRE_X0, GND_Y, z), (WIRE_X1, GND_Y, z)], (0.25, 0.25, 0.25, 1), 3)
        for x, al in ((WIRE_X0 + 0.1, "left"), (WIRE_X1 - 0.1, "right")):
            tx, rx = ("TX", "RX") if al == "left" else ("RX", "TX")
            self.label(tx, (x, TX_Y + 0.35, 0.3), 0.28, theme.TEXT_DIM, align=al)
            self.label(rx, (x, RX_Y + 0.35, 0.3), 0.28, theme.TEXT_DIM, align=al)
            self.label("GND", (x, GND_Y + 0.35, 0.3), 0.28, theme.TEXT_DIM, align=al)

        # 帧波形图
        self.wave = parts.Waveform(self.root, (WIRE_X0, 1.5, 3.2),
                                   WIRE_X1 - WIRE_X0, 0.8, theme.UART)
        self.wave.set_levels([1] * 12)
        cell = (WIRE_X1 - WIRE_X0) / 12
        names = ["空闲", "起始"] + ["b%d" % i for i in range(8)] + ["停止", "空闲"]
        for i, n in enumerate(names):
            self.label(n, (WIRE_X0 + cell * (i + 0.5), 1.5, 2.85), 0.22,
                       theme.TEXT_DIM)
        self.wave_bits = [self.label("", (WIRE_X0 + cell * (i + 0.5), 1.5, 4.3),
                                     0.3, theme.TEXT) for i in range(12)]
        self.cursor = self.box((0.06, 0.06, 1.3), (WIRE_X0, 1.45, 3.6), (1, 1, 1, 1))
        self.cursor.setLightOff(1)
        self.cursor.hide()
        self.label("TX 线上的电压（时间 →）", (WIRE_X0, 1.5, 4.8), 0.3, theme.UART,
                   align="left")

        # 接收移位寄存器
        self.rx_cells, self.rx_digits = [], []
        for bit in range(8):
            x = B_X - 3.6 + (7 - bit) * 0.7
            self.rx_cells.append(self.box((0.6, 0.6, 0.25), (x, -2.9, 0.15)))
            self.rx_digits.append(self.label("", (x, -2.9, 0.75), 0.35))
            self.label("b%d" % bit, (x, -3.5, 0.2), 0.2, theme.TEXT_DIM)
        self.label("接收寄存器", (B_X - 1.15, -2.1, 0.3), 0.3, theme.TEXT_DIM)
        self.rx_text = self.label("", (B_X, 4.0, 0.5), 0.4, theme.ACCENT)
        self.tx_text = self.label("", (A_X, -3.0, 0.5), 0.35, theme.TEXT)

        for ch in string.ascii_lowercase + string.digits:
            self.accept(ch, self.send, [ch])
        for ch in string.ascii_lowercase:
            self.accept("shift-" + ch, self.send, [ch.upper()])
        self.accept("space", self.send, ["Hi"])
        self.accept_keys(["arrow_up", "="], self.change_speed, [1])
        self.accept_keys(["arrow_down", "-"], self.change_speed, [-1])
        self.refresh()

    # ---------- 输入 ----------
    def send(self, text):
        if len(self.queue) < 20:
            self.queue.extend(text)
        self.refresh()

    def change_speed(self, d):
        self.speed_i = max(0, min(len(BIT_TIMES) - 1, self.speed_i + d))

    # ---------- 发送与接收 ----------
    def start_frame(self, ch):
        code = ord(ch)
        bits = [0] + [code >> i & 1 for i in range(8)] + [1]
        cubes = []
        for i, b in enumerate(bits):
            color = theme.HIGH if b else theme.LOW
            cube = self.box((0.5, 0.5, 0.5), (WIRE_X0, TX_Y, 0.45), color)
            cube.setLightOff(1)
            self.label(str(b), (0, 0, 0.55), 0.35, parent=cube)
            cube.hide()
            cubes.append(cube)
        self.frame = {"ch": ch, "bits": bits, "t": 0.0, "cubes": cubes,
                      "arrived": 0, "T": BIT_TIMES[self.speed_i]}
        self.rx_bits = [None] * 8
        self.wave.set_levels([1] + bits + [1])
        for i, lbl in enumerate(self.wave_bits):
            set_text(lbl, str(([1] + bits + [1])[i]) if 0 < i < 11 else "")
        self.cursor.show()
        self.refresh()

    def bit_arrived(self, i):
        f = self.frame
        b = f["bits"][i]
        if i == 0:
            self.rx_status = "检测到起始位 0，开始接收！"
        elif i <= 8:
            self.rx_bits[i - 1] = b
            self.rx_status = "收到 bit%d = %d" % (i - 1, b)
        else:
            self.received = (self.received + f["ch"])[-16:]
            self.rx_status = "收到停止位，一个字节接收完成：'%s'" % f["ch"]
        self.refresh()

    def finish_frame(self):
        for c in self.frame["cubes"]:
            c.removeNode()
        self.frame = None
        self.cursor.hide()
        self.gap = 0.4

    # ---------- 显示 ----------
    def refresh(self):
        for bit in range(8):
            v = self.rx_bits[bit]
            set_text(self.rx_digits[bit], "" if v is None else str(v))
            color = (0.25, 0.27, 0.32, 1) if not v else theme.ACCENT
            self.rx_cells[bit].setColor(*color, 1)
        set_text(self.rx_text, "B 收到：%s" % (self.received or "（空）"))
        set_text(self.tx_text, "待发送：%s" % ("".join(self.queue) or "（空）"))
        body = INTRO + "\n\n接收方状态：%s" % self.rx_status
        if self.frame:
            ch = self.frame["ch"]
            code = ord(ch)
            b = format(code, "08b")
            lsb = " ".join(b[::-1])
            body += ("\n\n正在发送 '%s'：ASCII 码 %d = 0x%02X = %s %s\n"
                     "实际发送顺序：0（起始） %s（低位先发） 1（停止）"
                     % (ch, code, code, b[:4], b[4:], lsb))
        self.set_body(body)

    def update(self, dt):
        if self.frame is None:
            self.gap = max(0.0, self.gap - dt)
            if self.queue and self.gap == 0.0:
                self.start_frame(self.queue.pop(0))
            self.tx_wire.setColor(*theme.HIGH[:3], 1, 1)
            return
        f = self.frame
        f["t"] += dt
        T = f["T"]
        v = SPACING / T
        length = WIRE_X1 - WIRE_X0
        for i, cube in enumerate(f["cubes"]):
            if cube.isEmpty():
                continue
            s = (f["t"] - i * T) * v
            if s < 0:
                continue
            if s >= length:
                if i >= f["arrived"]:
                    f["arrived"] = i + 1
                    self.bit_arrived(i)
                cube.hide()
                continue
            cube.show()
            cube.setX(WIRE_X0 + s)
        # 发送端引脚当前的电平
        idx = int(f["t"] / T)
        level = f["bits"][idx] if idx < len(f["bits"]) else 1
        c = theme.HIGH if level else theme.LOW
        self.tx_wire.setColor(c[0], c[1], c[2], 1, 1)
        cell = length / 12
        pos = min(f["t"] / T, 10.0)
        self.cursor.setX(WIRE_X0 + cell * (1 + pos))
        if f["arrived"] >= len(f["bits"]):
            self.finish_frame()
