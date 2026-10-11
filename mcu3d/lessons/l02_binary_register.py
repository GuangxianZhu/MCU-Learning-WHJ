"""第 2 课：二进制、字节与寄存器。"""

from ..schem.draw import ACTIVE, INK, INK_DIM, Canvas
from .base import Lesson

INTRO = ("单片机内部只认识两种状态：有电（1）和没电（0）。"
         "一个 0 或 1 叫做 1 位（bit），8 位放在一起叫 1 个字节（Byte）。\n\n"
         "每一位都有自己的“权重”：从右往左依次是 1、2、4、8 … 128。"
         "把为 1 的位的权重加起来，就是这个数的十进制值。\n\n"
         "十六进制：每 4 位二进制正好对应 1 个十六进制数字（0~9、A~F），"
         "所以 8 位只要写 2 个字符，例如 1010 0011 = 0xA3。程序员看寄存器时几乎都用十六进制。\n\n"
         "“寄存器”就是芯片里这样一排排的小格子（这里画的是 8 位，STM32 的寄存器一般是 32 位）。"
         "外设寄存器的每一位都连着一个真实的“开关”——"
         "下面那排 LED 就是在提前预告：到第 8 课，写寄存器就能点灯！\n\n"
         "电路图里，1 根线亮绿是 1、深绿是 0；右边粗一点的线是 4 根线并排（叫“总线”），"
         "送到十六进制数码管上显示。")

SEGMENTS = {  # 七段数码管每一段：(x0, z0, x1, z1)，以数码管左下角为原点，宽 2.4 高 4.4
    "a": (0.3, 4.0, 2.1, 4.4), "b": (2.0, 2.3, 2.4, 4.1), "c": (2.0, 0.3, 2.4, 2.1),
    "d": (0.3, 0.0, 2.1, 0.4), "e": (0.0, 0.3, 0.4, 2.1), "f": (0.0, 2.3, 0.4, 4.1),
    "g": (0.3, 2.0, 2.1, 2.4)}
DIGITS = ["abcdef", "bc", "abdeg", "abcdg", "bcfg", "acdfg", "acdefg", "abc", "abcdefg",
          "abcdfg", "abcefg", "cdefg", "adef", "bcdeg", "adefg", "aefg"]
SEG_ON = (0.95, 0.1, 0.05, 1)
SEG_OFF = (0.93, 0.88, 0.88, 1)
LED_ON = (0.1, 0.85, 0.15, 1)
LED_OFF = (0.12, 0.3, 0.14, 1)
CELL_ON = (1.0, 0.93, 0.62, 1)


def _bx(bit):
    return 3 + (7 - bit) * 4.2


class HexDigit:
    """Logisim 的“十六进制数码管”：输入 4 位，显示 0~F。"""

    def __init__(self, canvas, x, z):
        canvas.box(x - 0.5, z - 0.5, x + 2.9, z + 4.9, "", fill=(0.97, 0.97, 0.97, 1))
        self.segs = {k: canvas.box(x + x0, z + z0, x + x1, z + z1, "", fill=SEG_OFF)
                     for k, (x0, z0, x1, z1) in SEGMENTS.items()}
        for seg in self.segs.values():
            seg.edge.hide()     # 数码管的每一段只是一块亮或不亮的色块，不画黑边
            seg.fill.setY(-0.08)  # 放在底板前面一点

    def show(self, v):
        on = DIGITS[v & 0xF]
        for k, seg in self.segs.items():
            seg.set_fill(SEG_ON if k in on else SEG_OFF)


class BinaryRegister(Lesson):
    title = "二进制与寄存器"
    summary = "0 和 1、字节、寄存器、位操作"
    hints = ("1~8 翻转第 0~7 位   左键点上面的输入引脚也能翻转\n"
             "空格 加1   左右方向键 左移/右移   C 清零   A 自动计数")
    view2d = True
    bounds = (-2, 1, 46, 24)
    location = ["cpu", "gpio", "tim", "uart", "i2c", "adc"]
    location_text = (
        "寄存器分布在芯片的两类地方：\n"
        "① CPU 内部：R0~R12、PC 等通用寄存器，是 CPU 计算时临时放数的地方，没有地址；\n"
        "② 每个外设内部：GPIO 的 ODR、定时器的 ARR、串口的 TDR……"
        "它们是控制外设的“开关面板”，各自有固定地址（0x4000 0000 开始）。\n"
        "本课画面里的 8 个格子，可以当作 GPIOA 外设里输出寄存器 ODR 的低 8 位——"
        "第 8 课你会看到它真的控制引脚。")
    link_text = (
        "上一课说芯片里全是 0 和 1，这一课学怎么读写它们。下一课用十六进制写“地址”；第 6 课 ALU 做的就是二进制加法；第 8 课写寄存器的某一位就能点灯。按 S 可以在模拟器里看 |=、&= ~、^= 被 CPU 一步步执行。")
    apply_text = (
        "看懂芯片手册里的寄存器位定义图；会写 reg |= (1 << 5) 这样的置位、清零、翻转代码；能在二进制、十进制、十六进制之间换算。")
    sim_program = "bits"
    terms = ["二进制", "位", "字节", "十六进制", "寄存器", "外设寄存器", "地址", "位操作"]

    def setup(self):
        self.value = 0
        self.auto = False
        self.auto_t = 0.0
        self.last_op = "（还没有操作，试试按数字键 1）"

        c = self.canvas = Canvas(self)
        x0, z0, x1, z1 = self.bounds
        c.paper(x0, z0, x1, z1)
        self.value_text = c.text("", -1.5, 22.6, 0.8)
        c.text("输入引脚（点一下翻转）", -1.5, 20.9, 0.5, INK_DIM)
        frame = c.box(0.6, 8.6, 33.2, 15.2, "", fill=(0.96, 0.96, 0.96, 1))
        frame.fill.setY(0.08)   # 底板放在格子后面
        c.text("一个 8 位寄存器（比如 GPIOA 的 ODR 低 8 位）", 1.0, 14.4, 0.5, INK_DIM)
        self.pins, self.in_wires, self.cells, self.cell_text = [], [], [], []
        self.out_wires, self.leds = [], []
        for bit in range(8):
            x = _bx(bit)
            _, val = c.pin_in(x + 0.3, 18.5, "bit%d" % bit, tag="bit%d" % bit, label_side="top")
            self.pins.append(val)
            self.in_wires.append(c.wire([(x, 17.9), (x, 13.4)]))
            self.cells.append(c.box(x - 1.3, 9.4, x + 1.3, 13.4, "", tag="bit%d" % bit))
            self.cell_text.append(c.text("0", x, 10.6, 1.6, INK, "center"))
            c.text("权重 %d" % (1 << bit), x, 7.5, 0.5, ACTIVE, "center")
            self.out_wires.append(c.wire([(x, 9.4), (x, 5.3)]))
            self.leds.append(c.box(x - 0.8, 3.7, x + 0.8, 5.3, "", fill=LED_OFF))
        c.text("LED：寄存器的每一位接一个灯", -1.5, 2.2, 0.5, INK_DIM)
        hx = _bx(0) + 4.5
        c.text("十六进制数码管", hx + 2.9, 18.0, 0.5, INK_DIM, "center")
        self.hi_bus = c.wire([(33.2, 13.0), (34.4, 13.0), (34.4, 16.6), (hx + 1.2, 16.6),
                              (hx + 1.2, 14.4)], 4)
        self.lo_bus = c.wire([(33.2, 12.0), (35.2, 12.0), (35.2, 17.2), (hx + 4.8, 17.2),
                              (hx + 4.8, 14.4)], 4)
        self.digits = [HexDigit(c, hx, 9.4), HexDigit(c, hx + 3.6, 9.4)]
        c.text("高 4 位", hx + 1.2, 8.2, 0.45, INK_DIM, "center")
        c.text("低 4 位", hx + 4.8, 8.2, 0.45, INK_DIM, "center")

        for bit in range(8):
            self.accept(str(bit + 1), self.toggle, [bit])
        self.accept_keys(["space"], self.increment)
        self.accept_keys(["arrow_left"], self.shift, [1])
        self.accept_keys(["arrow_right"], self.shift, [-1])
        self.accept("c", self.clear)
        self.accept("a", self.toggle_auto)
        self.home()
        self.refresh()

    def home(self):
        self.app.fit_view(*self.bounds)

    # ---------- 操作 ----------
    def toggle(self, bit):
        self.value ^= (1 << bit)
        self.last_op = "reg ^= (1 << %d);   // 翻转第 %d 位" % (bit, bit)
        self.refresh()

    def on_pick(self, tag):
        if tag.startswith("bit"):
            self.toggle(int(tag[3:]))

    def on_double_pick(self, tag):
        self.on_pick(tag)

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
            on = v >> bit & 1
            self.pins[bit].node().setText(str(on))
            self.in_wires[bit].set(on)
            self.out_wires[bit].set(on)
            self.cells[bit].set_fill(CELL_ON if on else (1, 1, 1, 1))
            self.cell_text[bit].node().setText(str(on))
            self.leds[bit].set_fill(LED_ON if on else LED_OFF)
        self.hi_bus.set(v >> 4)
        self.lo_bus.set(v & 0xF)
        self.digits[0].show(v >> 4)
        self.digits[1].show(v & 0xF)
        b = format(v, "08b")
        self.value_text.node().setText("二进制 %s %s  =  十进制 %d  =  十六进制 0x%02X"
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
