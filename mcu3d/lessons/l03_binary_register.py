"""第 3 课：二进制、字节与寄存器。"""

from .. import parts, theme
from ..ui import set_text
from .base import Lesson

SPACING = 1.6

INTRO = ("单片机内部只认识两种状态：有电（1）和没电（0）。"
         "一个 0 或 1 叫做 1 位（bit），8 位放在一起叫 1 个字节（Byte）。\n\n"
         "每一位都有自己的“权重”：从右往左依次是 1、2、4、8 … 128。"
         "把为 1 的位的权重加起来，就是这个数的十进制值。\n\n"
         "“寄存器”就是芯片里这样一排排的小格子。"
         "有的寄存器存数据，有的寄存器的每一位都连着一个“开关”——"
         "下面那排 LED 就是在提前预告：下一课，写寄存器就能点灯！")


class BinaryRegister(Lesson):
    title = "二进制与寄存器"
    summary = "0 和 1、字节、寄存器、位操作"
    hints = ("1~8 翻转第 0~7 位   左键点方块也能翻转\n"
             "空格 加1   左右方向键 左移/右移   C 清零   A 自动计数")
    camera = (26, 0, -30, (0, -1.0, 1))

    def setup(self):
        self.value = 0
        self.auto = False
        self.auto_t = 0.0
        self.last_op = "（还没有操作，试试按数字键 1）"

        self.box((14.2, 2.4, 0.15), (0, 0, 0.05), (0.18, 0.2, 0.28, 1))
        self.label("一个 8 位寄存器（1 字节）", (-6.9, 1.6, 0.3), 0.38,
                   theme.TEXT_DIM, align="left")
        self.cubes = []
        self.digits = []
        self.leds = []
        for bit in range(8):
            x = (3.5 - bit) * SPACING
            cube = self.box((1.3, 1.3, 1.3), (x, 0, 0.8), (1, 1, 1, 1),
                            pick="bit%d" % bit)
            self.cubes.append(cube)
            self.digits.append(self.label("0", (x, 0, 2.1), 0.8))
            self.label("bit%d" % bit, (x, -1.6, 0.2), 0.32, theme.TEXT_DIM)
            self.label(str(1 << bit), (x, -2.2, 0.2), 0.36, theme.ACCENT)
            self.leds.append(parts.LED(self.root, (x, -4.0, 0),
                                       color=theme.LED_GREEN, radius=0.3))
        self.label("权重", (-7.2, -2.2, 0.2), 0.32, theme.TEXT_DIM, align="right")
        self.value_text = self.label("", (0, 1.5, 3.8), 0.45, theme.TEXT)

        for bit in range(8):
            self.accept(str(bit + 1), self.toggle, [bit])
        self.accept_keys(["space"], self.increment)
        self.accept_keys(["arrow_left"], self.shift, [1])
        self.accept_keys(["arrow_right"], self.shift, [-1])
        self.accept("c", self.clear)
        self.accept("a", self.toggle_auto)
        self.refresh()

    # ---------- 操作 ----------
    def toggle(self, bit):
        self.value ^= (1 << bit)
        self.last_op = "reg ^= (1 << %d);   // 翻转第 %d 位" % (bit, bit)
        self.refresh()

    def on_pick(self, tag):
        if tag.startswith("bit"):
            self.toggle(int(tag[3:]))

    def increment(self):
        self.value = (self.value + 1) & 0xFF
        self.last_op = "reg = reg + 1;   // 加 1（超过 255 会回到 0）"
        self.refresh()

    def shift(self, direction):
        if direction > 0:
            self.value = (self.value << 1) & 0xFF
            self.last_op = "reg = reg << 1;   // 左移：所有位往左挪，相当于 ×2"
        else:
            self.value >>= 1
            self.last_op = "reg = reg >> 1;   // 右移：所有位往右挪，相当于 ÷2"
        self.refresh()

    def clear(self):
        self.value = 0
        self.last_op = "reg = 0;   // 清零"
        self.refresh()

    def toggle_auto(self):
        self.auto = not self.auto

    # ---------- 显示 ----------
    def refresh(self):
        v = self.value
        for bit in range(8):
            on = bool(v >> bit & 1)
            self.cubes[bit].setColor(*(theme.ACCENT if on else (0.38, 0.4, 0.48, 1)), 1)
            set_text(self.digits[bit], "1" if on else "0")
            self.leds[bit].set_on(on)
        b = format(v, "08b")
        set_text(self.value_text, "二进制 %s %s  =  十进制 %d  =  十六进制 0x%02X"
                 % (b[:4], b[4:], v, v))
        parts_sum = [str(1 << i) for i in range(7, -1, -1) if v >> i & 1]
        breakdown = " + ".join(parts_sum) if parts_sum else "0"
        self.set_body(
            INTRO + "\n\n"
            "当前值：%d = %s\n\n"
            "刚才执行的 C 语言代码：\n%s\n\n"
            "常用位操作（以后会天天用）：\n"
            "reg |=  (1 << n);  把第 n 位置 1\n"
            "reg &= ~(1 << n);  把第 n 位清 0\n"
            "reg ^=  (1 << n);  把第 n 位翻转"
            % (v, breakdown, self.last_op))

    def update(self, dt):
        if self.auto:
            self.auto_t += dt
            if self.auto_t > 0.4:
                self.auto_t = 0.0
                self.increment()
