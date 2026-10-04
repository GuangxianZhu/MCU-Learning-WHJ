"""第 4 课：GPIO——用寄存器控制引脚。"""

from .. import parts, theme
from ..ui import set_text
from .base import Lesson

LED_X = 5.0
CHIP_POS = (-3.0, 0.0, 0)

MODES = [
    ("手动模式",
     "按数字键 1~8，直接修改 GPIOA 的输出寄存器 ODR 的第 0~7 位。\n"
     "相当于程序执行了：\n"
     "GPIOA->ODR ^= (1 << n);"),
    ("程序：流水灯",
     "while (1) {\n"
     "    GPIOA->ODR = 1 << i;  // 只点亮第 i 个灯\n"
     "    delay_ms(300);\n"
     "    i = (i + 1) % 8;      // 换下一个\n"
     "}"),
    ("程序：按键控制",
     "while (1) {\n"
     "    if (GPIOB->IDR & 1)     // 读按键引脚\n"
     "        GPIOA->ODR = 0xFF;  // 按下：全亮\n"
     "    else\n"
     "        GPIOA->ODR = 0x00;  // 松开：全灭\n"
     "}\n"
     "按住 B 键模拟按下按键试试。"),
    ("程序：二进制计数",
     "while (1) {\n"
     "    GPIOA->ODR = count;   // 把数字直接写到引脚\n"
     "    count++;\n"
     "    delay_ms(400);\n"
     "}\n"
     "看，上一课的二进制数字变成了灯！"),
]

INTRO = ("GPIO（General Purpose Input/Output）= 通用输入输出口。\n\n"
         "MCU 的每个引脚都连着寄存器里的某一位：\n"
         "· 输出：往输出寄存器 ODR 写 1，引脚就输出 3.3V（高电平），LED 亮；"
         "写 0 输出 0V（低电平），LED 灭。\n"
         "· 输入：引脚上的电压会被记录到输入寄存器 IDR，程序读它就知道按键状态。\n\n"
         "引脚按组命名：PA0~PA15 属于 A 组（GPIOA），PB0 属于 B 组……\n"
         "代码里的 GPIOA->ODR 是 C 语言写法，意思是“GPIOA 这个外设里的 ODR 寄存器”。\n"
         "（真实芯片里还要先通过 MODER 寄存器把引脚设成输出或输入，这里省略。）\n\n"
         "导线颜色：橙色 = 高电平 3.3V，蓝色 = 低电平 0V。")


class GPIOLesson(Lesson):
    title = "GPIO 输入输出"
    summary = "写寄存器点灯，读寄存器知道按键"
    hints = "1~8 翻转 PA0~PA7   按住 B 按下按键   空格 切换程序"
    camera = (29, 0, -52, (0.5, 0, 0))
    location = ["gpio", "bus", "pins"]
    location_text = (
        "GPIO 外设（芯片下排橙色那块）和它连着的引脚。ODR、IDR、MODER 这几个寄存器"
        "都长在 GPIO 外设里面。以 STM32F103 为例，GPIOA 的寄存器从地址 0x4001 0800 开始，"
        "其中 ODR 在 0x4001 080C。CPU 经过总线往这个地址写数字，"
        "GPIO 外设就按每一位去改变对应引脚的电压。")
    terms = ["GPIO", "端口", "电平", "ODR", "IDR", "MODER"]

    def setup(self):
        self.odr = 0
        self.idr = 0
        self.mode = 0
        self.prog_t = 0.0
        self.prog_i = 0

        self.box((18, 13, 0.3), (0.5, 0.3, -0.15), theme.PCB)
        self.chip = parts.Chip(self.root, size=4, pos=CHIP_POS, label="MCU")
        self.label("MCU", (CHIP_POS[0], CHIP_POS[1] + 3.3, 0.5), 0.4, theme.TEXT_DIM)

        self.leds = []
        self.out_wires = []
        for i in range(8):
            y = -3.5 + i
            px, py, _ = self.chip.pin_pos(0, i)
            w = self.wire([(px, py, 0.15), (0.5 + i * 0.25, py, 0.15),
                           (0.5 + i * 0.25, y, 0.15), (LED_X - 0.4, y, 0.15)],
                          thickness=4)
            self.out_wires.append(w)
            self.leds.append(parts.LED(self.root, (LED_X, y, 0), radius=0.3))
            self.label("PA%d" % i, (LED_X + 1.1, y, 0.3), 0.32, theme.TEXT_DIM,
                       align="left")

        # 按键接在 PB0 上
        self.button = parts.Button(self.root, (CHIP_POS[0], -5.0, 0), label=None)
        self.label("按键 PB0（按住 B）", (CHIP_POS[0] - 1.0, -5.0, 0.5), 0.32,
                   theme.TEXT_DIM, align="right")
        bx, by, _ = self.chip.pin_pos(3, 3)
        self.in_wire = self.wire([(bx, by, 0.15), (bx, -4.4, 0.15),
                                  (CHIP_POS[0], -4.4, 0.15)], thickness=4)

        # 寄存器显示
        self.reg_cells = []
        self.reg_digits = []
        self.label("GPIOA->ODR\n（GPIOA 外设里\n地址 0x4001080C）", (-7.3, 6.0, 0.4), 0.32, theme.ACCENT, align="left")
        for bit in range(8):
            x = -2.5 + (7 - bit) * 0.95
            self.reg_cells.append(self.box((0.8, 0.8, 0.3), (x, 5.6, 0.15)))
            self.reg_digits.append(self.label("0", (x, 5.6, 0.9), 0.45))
            self.label(str(bit), (x, 4.9, 0.3), 0.26, theme.TEXT_DIM)
        self.label("GPIOB->IDR 第0位", (-1.8, -5.0, 0.4), 0.32, theme.ACCENT,
                   align="left")
        self.idr_cell = self.box((0.8, 0.8, 0.3), (2.6, -5.0, 0.15))
        self.idr_digit = self.label("0", (2.6, -5.0, 0.9), 0.45)

        for i in range(8):
            self.accept(str(i + 1), self.toggle_bit, [i])
        self.accept("b", self.set_button, [True])
        self.accept("b-up", self.set_button, [False])
        self.accept("space", self.next_mode)
        self.refresh()

    # ---------- 输入 ----------
    def toggle_bit(self, i):
        if self.mode != 0:
            self.mode = 0
            self.odr = 0
        self.odr ^= 1 << i
        self.refresh()

    def set_button(self, pressed):
        self.button.set_pressed(pressed)
        self.idr = 1 if pressed else 0
        self.refresh()

    def next_mode(self):
        self.mode = (self.mode + 1) % len(MODES)
        self.prog_t = 0.0
        self.prog_i = 0
        self.odr = 0
        self.refresh()

    # ---------- 显示 ----------
    def refresh(self):
        for i in range(8):
            on = bool(self.odr >> i & 1)
            self.leds[i].set_on(on)
            c = theme.HIGH if on else theme.LOW
            self.out_wires[i].setColor(c[0], c[1], c[2], 1, 1)
            self.reg_cells[i].setColor(*(theme.ACCENT if on else (0.25, 0.27, 0.32, 1)), 1)
            set_text(self.reg_digits[i], "1" if on else "0")
        c = theme.HIGH if self.idr else theme.LOW
        self.in_wire.setColor(c[0], c[1], c[2], 1, 1)
        self.idr_cell.setColor(*(theme.ACCENT if self.idr else (0.25, 0.27, 0.32, 1)), 1)
        set_text(self.idr_digit, str(self.idr))

        name, code = MODES[self.mode]
        self.set_body(INTRO + "\n\n【%s】（空格切换）\n%s\n\nODR = 0x%02X   IDR 第0位 = %d"
                      % (name, code, self.odr, self.idr))

    def update(self, dt):
        if self.mode == 0:
            return
        new = self.odr
        if self.mode == 2:
            new = 0xFF if self.idr else 0x00
        else:
            self.prog_t += dt
            period = 0.3 if self.mode == 1 else 0.4
            if self.prog_t >= period:
                self.prog_t -= period
                self.prog_i += 1
            if self.mode == 1:
                new = 1 << (self.prog_i % 8)
            else:
                new = self.prog_i & 0xFF
        if new != self.odr:
            self.odr = new
            self.refresh()
