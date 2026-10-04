"""第 13 课：ADC 模数转换。"""

import math

from .. import parts, shapes, theme
from ..ui import set_text
from .base import Lesson

VREF = 3.3
RESOLUTIONS = [3, 4, 8, 12]
SAMPLE_RATES = [1, 2, 5, 10, 30]
SIM_HZ = 30
HISTORY = 150                    # 画面上保留的点数（5 秒）
PLOT_X0, PLOT_W = -0.5, 10.5
PLOT_Y = 1.5
PLOT_Z0, PLOT_H = 0.4, 5.0

INTRO = (
    "真实世界里的温度、光线、声音都是“连续变化”的，传感器把它们变成 0~3.3V 之间的电压。"
    "但 CPU 只认识数字，于是需要 ADC（模数转换器）。\n\n"
    "ADC 做两件事：\n"
    "① 采样：每隔一段时间“拍一张照”，记下这一刻的电压\n"
    "② 量化：把电压换成最接近的整数。n 位 ADC 能分 2ⁿ 个台阶\n\n"
    "读数 = 电压 ÷ 3.3V × (2ⁿ - 1)\n"
    "电压 = 读数 ÷ (2ⁿ - 1) × 3.3V\n\n"
    "右边的图：青色是真实电压（连续的曲线），橙色是 ADC 读到的数字（一级一级的台阶）。"
    "位数越多台阶越细，采样越快台阶越窄，就越接近真实曲线。"
    "常见的 STM32 是 12 位 ADC：0~4095。\n\n"
    "下面的 LED 亮度 = 读数，这就是“旋钮调光”程序。")


class ADCLesson(Lesson):
    title = "ADC 模数转换"
    summary = "把温度、光线变成数字"
    hints = ("左右方向键 转动旋钮   A 自动变化\n"
             "R 切换位数（3/4/8/12 位）   上下方向键 调采样速度")
    camera = (36, 0, -26, (1.2, -0.5, 2.8))
    location = ["adc", "bus", "pins"]
    location_text = (
        "ADC 外设（芯片下排绿色那块）。外面的电压从一个引脚进入 ADC，"
        "转换结果放在 ADC 的数据寄存器 ADC_DR 里（ADC1 从地址 0x4001 2400 开始），"
        "CPU 经总线读这个寄存器就得到读数。")
    link_text = (
        "ADC 的结果是一个二进制数（第 2 课），CPU 从 ADC_DR 寄存器把它读回来（第 4 课的总线读）；转换完成也可以触发中断（第 10 课）。下一课用它读温度。")
    apply_text = (
        "读温度、光线、电池电压、摇杆位置。温度报警器用它读热敏电阻的电压，换算成温度。")
    sim_program = "inc"
    terms = ["模拟信号", "数字信号", "ADC", "采样", "量化", "分辨率", "参考电压", "电位器"]

    def setup(self):
        self.voltage = 1.2
        self.auto = True
        self.res_i = 0
        self.rate_i = 2
        self.sim_acc = 0.0
        self.sample_acc = 0.0
        self.reading = 0
        self.analog = []
        self.digital = []
        self.grid = None
        self.curve_np = None
        self.stairs_np = None

        self.box((22, 9, 0.2), (0, -1.0, -0.1), theme.PCB)

        # 电位器
        self.box((1.8, 1.8, 0.5), (-8.0, -2.0, 0.25), (0.25, 0.3, 0.6, 1))
        self.knob = shapes.cylinder(0.6, 0.7, (0.85, 0.85, 0.85, 1))
        self.knob.reparentTo(self.root)
        self.knob.setPos(-8.0, -2.0, 0.5)
        self.box((0.15, 0.6, 0.12), (0, 0.3, 0.75), theme.LED_RED, parent=self.knob)
        self.label("电位器（旋钮）", (-8.0, -2.0, 2.0), 0.32)
        self.pot_text = self.label("", (-8.0, -3.6, 0.3), 0.32, theme.UART)

        # MCU
        self.chip = parts.Chip(self.root, size=3, pos=(-3.6, -2.0, 0), label="ADC")
        self.label("MCU", (-3.6, -0.2, 0.4), 0.32, theme.TEXT_DIM)
        self.wire([(-7.1, -2.0, 0.2), (-5.5, -2.0, 0.2)], theme.UART, 5)
        self.label("ADC 引脚", (-6.3, -1.6, 0.3), 0.26, theme.TEXT_DIM)
        self.led = parts.LED(self.root, (-3.6, -5.0, 0), color=theme.LED_GREEN,
                             label=None)
        self.wire([(-3.6, -3.95, 0.2), (-3.6, -4.6, 0.2)], theme.TEXT_DIM, 3)
        self.label("LED 亮度 = 读数", (-1.8, -5.0, 0.4), 0.28, theme.TEXT_DIM,
                   align="left")

        # 曲线图
        frame = self.box((PLOT_W + 0.4, 0.1, PLOT_H + 0.4),
                         (PLOT_X0 + PLOT_W / 2, PLOT_Y + 0.15, PLOT_Z0 + PLOT_H / 2),
                         (0.1, 0.11, 0.16, 1))
        frame.setLightOff(1)
        self.label("3.3V", (PLOT_X0 - 0.2, PLOT_Y, PLOT_Z0 + PLOT_H), 0.28,
                   theme.TEXT_DIM, align="right")
        self.label("0V", (PLOT_X0 - 0.2, PLOT_Y, PLOT_Z0), 0.28, theme.TEXT_DIM,
                   align="right")
        self.label("时间 →", (PLOT_X0 + PLOT_W, PLOT_Y, PLOT_Z0 - 0.5), 0.28,
                   theme.TEXT_DIM, align="right")
        self.value_text = self.label("", (PLOT_X0 + PLOT_W / 2, PLOT_Y,
                                          PLOT_Z0 + PLOT_H + 1.0), 0.4)
        self.grid_text = self.label("", (PLOT_X0 + PLOT_W / 2, PLOT_Y,
                                         PLOT_Z0 + PLOT_H + 0.45), 0.28,
                                    theme.TEXT_DIM)

        self.accept_keys(["arrow_left"], self.turn, [-0.1])
        self.accept_keys(["arrow_right"], self.turn, [0.1])
        self.accept("a", self.toggle_auto)
        self.accept("r", self.next_res)
        self.accept_keys(["arrow_up"], self.change_rate, [1])
        self.accept_keys(["arrow_down"], self.change_rate, [-1])
        self.draw_grid()
        self.sample()
        self.refresh()

    # ---------- 输入 ----------
    def turn(self, dv):
        self.auto = False
        self.voltage = max(0.0, min(VREF, self.voltage + dv))

    def toggle_auto(self):
        self.auto = not self.auto
        self.refresh()

    def next_res(self):
        self.res_i = (self.res_i + 1) % len(RESOLUTIONS)
        self.draw_grid()
        self.sample()
        self.refresh()

    def change_rate(self, d):
        self.rate_i = max(0, min(len(SAMPLE_RATES) - 1, self.rate_i + d))
        self.refresh()

    # ---------- 逻辑 ----------
    @property
    def bits(self):
        return RESOLUTIONS[self.res_i]

    @property
    def max_code(self):
        return (1 << self.bits) - 1

    def sample(self):
        self.reading = int(round(self.voltage / VREF * self.max_code))
        self.led.set_level(self.reading / self.max_code)
        self.refresh()

    def to_z(self, v):
        return PLOT_Z0 + PLOT_H * v / VREF

    def draw_grid(self):
        if self.grid is not None:
            self.grid.removeNode()
        self.grid = self.root.attachNewNode("grid")
        levels = self.max_code
        if levels <= 16:
            for k in range(levels + 1):
                z = self.to_z(k / levels * VREF)
                self.wire([(PLOT_X0, PLOT_Y, z), (PLOT_X0 + PLOT_W, PLOT_Y, z)],
                          (0.25, 0.27, 0.35, 1), 1, parent=self.grid)
                self.label(str(k), (PLOT_X0 + PLOT_W + 0.3, PLOT_Y, z - 0.1), 0.22,
                           theme.TIMER, align="left", parent=self.grid)
            set_text(self.grid_text, "%d 位 ADC：%d 个台阶（右边数字是读数）"
                     % (self.bits, levels + 1))
        else:
            set_text(self.grid_text, "%d 位 ADC：%d 个台阶，细到画不出来了"
                     % (self.bits, levels + 1))

    def redraw_plot(self):
        for attr in ("curve_np", "stairs_np"):
            np = getattr(self, attr)
            if np is not None:
                np.removeNode()
        step = PLOT_W / HISTORY
        if len(self.analog) >= 2:
            pts = [(PLOT_X0 + i * step, PLOT_Y - 0.05, self.to_z(v))
                   for i, v in enumerate(self.analog)]
            self.curve_np = self.wire(pts, theme.UART, 2.5)
            pts = []
            for i, v in enumerate(self.digital):
                z = self.to_z(v)
                pts.append((PLOT_X0 + i * step, PLOT_Y - 0.1, z))
                pts.append((PLOT_X0 + (i + 1) * step, PLOT_Y - 0.1, z))
            self.stairs_np = self.wire(pts, theme.HIGH, 3.5)

    def refresh(self):
        v_read = self.reading / self.max_code * VREF
        set_text(self.value_text, "电压 %.2fV  →  读数 %d / %d  （二进制 %s）"
                 % (self.voltage, self.reading, self.max_code,
                    format(self.reading, "0%db" % self.bits)))
        set_text(self.pot_text, "%.2f V" % self.voltage)
        self.set_body(
            INTRO + "\n\n当前：%d 位，每秒采样 %d 次，%s\n"
            "读数 %d 换算回电压 = %d ÷ %d × 3.3 = %.3f V（误差 %.3f V）"
            % (self.bits, SAMPLE_RATES[self.rate_i],
               "自动变化中（A 停止）" if self.auto else "手动（A 自动）",
               self.reading, self.reading, self.max_code, v_read,
               abs(v_read - self.voltage)))

    def update(self, dt):
        if self.auto:
            self.voltage = VREF * (0.5 + 0.42 * math.sin(self.time * 0.9)
                                   + 0.06 * math.sin(self.time * 3.1))
        self.knob.setH(-self.voltage / VREF * 270 + 135)
        set_text(self.pot_text, "%.2f V" % self.voltage)

        self.sample_acc += dt
        period = 1.0 / SAMPLE_RATES[self.rate_i]
        if self.sample_acc >= period:
            self.sample_acc %= period
            self.sample()

        self.sim_acc += dt
        changed = False
        while self.sim_acc >= 1.0 / SIM_HZ:
            self.sim_acc -= 1.0 / SIM_HZ
            self.analog = (self.analog + [self.voltage])[-HISTORY:]
            self.digital = (self.digital + [self.reading / self.max_code * VREF])[-HISTORY:]
            changed = True
        if changed:
            self.redraw_plot()
