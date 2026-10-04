"""第 9 课：定时器与 PWM。"""

from .. import parts, theme
from ..ui import set_text
from .base import Lesson

COL_X = -2.5        # 计数器柱子的位置
COL_H = 6.0         # 柱子满高度
MAXV = 100          # 柱子满高度对应的计数值
SLOW, FAST = 40.0, 4000.0   # 每秒计数次数（演示）

INTRO_TIMER = (
    "定时器是一个会自己数数的外设，里面有几个关键寄存器：CNT（当前数到几）、"
    "PSC（预分频，给时钟减速）、ARR（数到几就归零）。\n\n"
    "定时器的核心是计数器 CNT：时钟每来一拍（先经过“预分频器”PSC 减速），"
    "CNT 就加 1。\n\n"
    "当 CNT 数到“自动重装值”ARR 时，它会归零重新开始，"
    "同时产生一次“更新事件”，可以触发中断。\n\n"
    "【定时中断模式】每次更新事件，中断里把 LED 取反，于是 LED 有规律地闪烁。"
    "ARR 越大，数得越久，闪得越慢。\n\n"
    "定时时间 = (PSC+1) × (ARR+1) ÷ 时钟频率\n"
    "例：72MHz 时钟，PSC = 7199，ARR = 9999，"
    "正好 1 秒中断一次。")

INTRO_PWM = (
    "【PWM 模式】再加一个“比较值”CCR：\n"
    "CNT < CCR 时引脚输出高电平，CNT ≥ CCR 时输出低电平。\n\n"
    "于是引脚输出一串方波。高电平占整个周期的比例叫“占空比”。\n\n"
    "当方波足够快（每秒几千次），人眼看不出闪烁，只会觉得 LED 变暗或变亮："
    "占空比 30% 看起来就是 30% 的亮度。电机也一样，占空比越大转得越快。\n\n"
    "按 F 切换“慢速 / 真实速度”，对比看看。")


class TimerPWM(Lesson):
    title = "定时器与 PWM"
    summary = "会自己数数的秒表，和调节亮度的魔法"
    hints = "空格 切换 定时中断/PWM 模式   上下方向键 调整 ARR/CCR   F 慢速/真实速度"
    camera = (30, 0, -18, (-1.5, 0, 2.4))
    location = ["tim", "clock", "gpio", "pins"]
    location_text = (
        "定时器外设 TIM（芯片下排黄色那块）。CNT、PSC、ARR、CCR 都是定时器外设里的寄存器"
        "（TIM2 从地址 0x4000 0000 开始）；计数用的时钟来自 RCC；"
        "PWM 要从引脚输出，所以借用一个 GPIO 引脚，把它设成“复用功能”交给定时器控制。")
    link_text = (
        "定时器和 GPIO 一样，用写寄存器（PSC、ARR、CCR）来设置；它数满一圈产生的“更新事件”，就是下一课中断的来源之一。")
    apply_text = (
        "精确定时、调 LED 亮度、控制电机和舵机。温度报警器里用 PWM 驱动蜂鸣器。")
    sim_program = "inc"
    terms = ["定时器", "CNT", "PSC", "ARR", "CCR", "更新事件", "PWM", "占空比", "频率"]

    def setup(self):
        self.mode = 0
        self.arr = 59
        self.wraps = 0
        self.ccr = 30
        self.cnt = 0
        self.count_t = 0.0
        self.fast = False
        self.led_on = False
        self.uev_flash = 0.0
        self.psc_flash = 0.0
        self.high_time = 0.0
        self.total_time = 0.0

        self.box((22, 6, 0.2), (1, 0, -0.1), (0.12, 0.13, 0.17, 1))

        # 时钟 → 预分频 → 计数器
        self.clock_box = self.box((1.6, 1.2, 1.0), (-9.0, 0, 0.5), theme.CLOCK)
        self.label("系统时钟", (-9.0, 0, 1.6), 0.35)
        self.psc_box = self.box((1.6, 1.2, 1.0), (-6.2, 0, 0.5), (0.5, 0.5, 0.6, 1))
        self.label("预分频 PSC", (-6.2, 0, 1.6), 0.35)
        self.label("÷(PSC+1)", (-6.2, -0.7, 0.5), 0.28, theme.TEXT_DIM)
        self.wire([(-8.2, 0, 0.5), (-7.0, 0, 0.5)], theme.CLOCK, 4)
        self.wire([(-5.4, 0, 0.5), (COL_X - 0.8, 0, 0.5)], theme.TEXT_DIM, 4)

        # 计数器柱子
        frame = self.box((1.5, 1.5, COL_H), (COL_X, 0, COL_H / 2), (0.6, 0.7, 0.9, 1))
        frame.setTransparency(True)
        frame.setAlphaScale(0.12)
        frame.setDepthWrite(False)
        self.bar = self.box((1.2, 1.2, 1.0), (COL_X, 0, 0), theme.TIMER)
        self.cnt_text = self.label("", (COL_X, 0, COL_H + 0.9), 0.45, theme.TIMER)
        self.label("计数器 CNT", (COL_X, 0, -0.6), 0.35)
        self.arr_plane = self.box((2.6, 2.0, 0.06), (COL_X, 0, 0), (1, 1, 1, 1))
        self.arr_text = self.label("", (COL_X + 1.5, 0, 0), 0.3, align="left")
        self.ccr_plane = self.box((2.6, 2.0, 0.06), (COL_X, 0, 0), theme.HIGH)
        self.ccr_text = self.label("", (COL_X + 1.5, 0, 0), 0.3, theme.HIGH,
                                   align="left")

        # 更新事件指示
        self.uev = self.box((1.8, 1.0, 0.6), (1.5, 0, 0.3), (0.3, 0.25, 0.1, 1))
        self.label("更新事件\n（中断）", (1.5, 0, 1.5), 0.3)

        # 输出：LED 与波形
        self.led = parts.LED(self.root, (5.0, 0, 0), label="输出引脚的 LED")
        self.wire([(COL_X + 0.8, 0, 0.3), (0.6, 0, 0.3)], theme.TEXT_DIM, 3)
        self.wire([(2.4, 0, 0.3), (4.6, 0, 0.3)], theme.TEXT_DIM, 3)
        self.wave = parts.Waveform(self.root, (1.5, 0.5, 2.6), 8.5, 1.0, theme.HIGH)
        self.label("输出波形", (1.5, 0.5, 4.0), 0.35, theme.HIGH, align="left")
        self.cursor = self.box((0.06, 0.06, 1.4), (1.5, 0.45, 3.1), (1, 1, 1, 1))
        self.cursor.setLightOff(1)

        self.accept("space", self.toggle_mode)
        self.accept_keys(["arrow_up", "="], self.adjust, [10])
        self.accept_keys(["arrow_down", "-"], self.adjust, [-10])
        self.accept("f", self.toggle_fast)
        self.refresh()

    # ---------- 输入 ----------
    def toggle_mode(self):
        self.mode = 1 - self.mode
        self.cnt = 0
        self.wraps = 0
        self.arr = 99 if self.mode == 1 else 59
        self.refresh()

    def adjust(self, d):
        if self.mode == 0:
            self.arr = max(19, min(99, self.arr + d))
            self.cnt = min(self.cnt, self.arr)
        else:
            self.ccr = max(0, min(100, self.ccr + d))
        self.refresh()

    def toggle_fast(self):
        self.fast = not self.fast
        self.refresh()

    # ---------- 逻辑 ----------
    def output_high(self):
        if self.mode == 0:
            return self.led_on
        return self.cnt < self.ccr

    def count(self):
        self.psc_flash = 0.08
        if self.cnt >= self.arr:
            self.cnt = 0
            self.wraps += 1
            self.uev_flash = 0.25
            if self.mode == 0:
                self.led_on = not self.led_on
        else:
            self.cnt += 1

    def refresh(self):
        h_arr = COL_H * self.arr / MAXV
        self.arr_plane.setZ(h_arr)
        self.arr_text.setZ(h_arr)
        set_text(self.arr_text, "ARR = %d（数到这里归零）" % self.arr)
        if self.mode == 1:
            self.ccr_plane.show()
            self.ccr_text.show()
            h = COL_H * self.ccr / MAXV
            self.ccr_plane.setZ(h)
            self.ccr_text.setZ(h - 0.4)
            set_text(self.ccr_text, "CCR = %d（占空比 %d%%）"
                     % (self.ccr, round(100 * self.ccr / (self.arr + 1))))
        else:
            self.ccr_plane.hide()
            self.ccr_text.hide()
        # 理想波形：画 3 个周期
        n = self.arr + 1
        if self.mode == 0:
            levels = ([1] * 4 + [0] * 4) * 3
        else:
            period = [1 if i < self.ccr else 0 for i in range(n)]
            levels = period * 3
        self.wave.set_levels(levels)
        speed = "真实速度（每秒 %d 次计数）" % FAST if self.fast else "慢速演示"
        if self.mode == 0:
            body = INTRO_TIMER + "\n\n当前：ARR = %d，%s" % (self.arr, speed)
        else:
            body = INTRO_PWM + "\n\n当前：CCR = %d / ARR+1 = %d，占空比 %d%%，%s" % (
                self.ccr, n, round(100 * self.ccr / n), speed)
        self.set_body(body)

    def update(self, dt):
        rate = FAST if self.fast else SLOW
        self.count_t += dt * rate
        high = 0
        steps = 0
        while self.count_t >= 1.0:
            self.count_t -= 1.0
            self.count()
            steps += 1
            high += self.output_high()
        h = max(self.cnt, 0.02) * COL_H / MAXV
        self.bar.setSz(h)
        self.bar.setZ(h / 2)
        set_text(self.cnt_text, "CNT = %d" % self.cnt)

        # LED：慢速时直接跟随输出；真实速度下人眼看到的是平均亮度
        if self.fast and self.mode == 1 and steps:
            self.led.set_level(high / steps)
        else:
            self.led.set_on(self.output_high())

        # 波形上的光标
        n = self.arr + 1
        if self.mode == 0:
            phase = ((self.wraps + 1) % 2 + self.cnt / n) / 2
            frac = ((self.wraps + 1) // 2 % 3 + phase) / 3
        else:
            frac = (self.wraps % 3 + self.cnt / n) / 3
        self.cursor.setX(1.5 + 8.5 * frac)

        self.uev_flash = max(0.0, self.uev_flash - dt)
        self.psc_flash = max(0.0, self.psc_flash - dt)
        u = 3.0 if self.uev_flash > 0 else 1.0
        self.uev.setColorScale(u, u, u, 1)
        p = 1.8 if self.psc_flash > 0 else 1.0
        self.psc_box.setColorScale(p, p, p, 1)
        k = 1.0 + 0.5 * parts.pulse(self.time, 40)
        self.clock_box.setColorScale(k, k, k, 1)
