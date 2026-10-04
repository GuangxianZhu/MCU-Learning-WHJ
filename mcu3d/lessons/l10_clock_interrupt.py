"""第 10 课：时钟与中断。"""

from .. import parts, theme
from ..ui import set_text
from .base import Lesson

MAIN = ["读取温度传感器", "计算平均值", "刷新显示屏", "等待一会儿", "跳回开头"]
ISR = ["保存现场（压栈）", "处理：LED 取反", "清除中断标志", "恢复现场并返回"]
SPEEDS = [0.5, 1, 2, 4, 8]

X_CLOCK, X_MAIN, X_ISR, X_STACK = -7.5, -2.5, 3.2, 7.8
SLAB_TOP, SLAB_STEP = 4.0, 0.9

INTRO = ("【时钟】晶振不停地产生“高-低-高-低”的方波，每一次上升沿就是一拍。"
         "CPU 跟着节拍执行指令（这里简化成一拍执行一条）。"
         "左列旁边的“PC →”就是程序计数器 PC：CPU 里记着“下一条执行哪一行”的寄存器。"
         "时钟频率越高，程序跑得越快。真实的 MCU 每秒有几千万拍，这里放慢了很多。\n\n"
         "【中断】主程序（左列）一直在循环做自己的事。按下按键时，"
         "中断控制器发出“中断请求”，CPU 执行完当前这条指令后，"
         "立刻跳到“中断服务函数”（右列）去处理，处理完再回到刚才的位置继续。\n\n"
         "跳过去之前，CPU 会把“回来的地址”和寄存器的值存进“栈”（最右边），"
         "回来时再取出来——这叫保存现场 / 恢复现场。\n\n"
         "【为什么要中断？】如果不用中断，主程序只能隔一会儿检查一次按键（轮询），"
         "可能会漏掉或反应很慢。中断就像门铃：不用一直盯着门口，铃响了再去开门。")


class ClockInterrupt(Lesson):
    title = "时钟与中断"
    summary = "心跳节拍，以及“先处理急事”"
    hints = "空格 按下按键（触发中断）   上下方向键 调整时钟快慢"
    camera = (36, 0, -14, (0.8, 0, 2.6))
    location = ["clock", "cpu", "nvic", "sram", "gpio", "pins"]
    location_text = (
        "时钟（RCC 模块 + 芯片外的晶振）、CPU 内核、中断控制器 NVIC 和 SRAM。"
        "PC 是 CPU 内部的寄存器；栈是 SRAM 里划出来的一块区域；"
        "按键接在 GPIO 引脚上，引脚电平变化经“外部中断”线路把请求送到 NVIC，"
        "再由 NVIC 通知 CPU。")
    link_text = (
        "中断用到第 7 课的栈：CPU 跳去处理中断前，要把“回来的地址”和寄存器压进栈。上一课定时器的更新事件、下一课 UART 收到数据，都可以触发中断。")
    apply_text = (
        "用中断代替“一直问”（轮询）；知道中断服务函数为什么要写得短。温度报警器用定时器中断每 0.5 秒采一次温度。")
    sim_program = "calls"
    terms = ["时钟", "晶振", "频率", "指令", "PC", "中断", "NVIC", "ISR", "栈", "现场",
             "轮询"]

    def setup(self):
        self.speed_i = 1
        self.half_t = 0.0
        self.level = 0
        self.levels = [0] * 40
        self.mode = "main"
        self.idx = 0
        self.saved_idx = 0
        self.pending = False
        self.press_t = 0.0
        self.led_on = False
        self.irq_count = 0

        self.box((20, 5, 0.2), (0, 0, -0.9), (0.12, 0.13, 0.17, 1))

        # 晶振与时钟波形
        self.box((1.6, 0.8, 0.6), (X_CLOCK, 0, 3.0), (0.8, 0.8, 0.85, 1))
        self.label("晶振", (X_CLOCK, 0, 3.8), 0.4)
        self.freq_text = self.label("", (X_CLOCK, 0, 2.2), 0.32, theme.TEXT_DIM)
        self.wave = parts.Waveform(self.root, (-9.5, 0.5, 5.9), 19, 0.8,
                                   theme.CLOCK)
        self.label("时钟信号", (-9.6, 0.5, 6.25), 0.35, theme.CLOCK, align="right")

        # 主程序与中断服务函数
        self.label("主程序 main()", (X_MAIN, 0, 4.8), 0.42, theme.ACCENT)
        self.label("中断服务函数 ISR", (X_ISR, 0, 4.8), 0.42, theme.NVIC)
        self.main_slabs = [self._slab(X_MAIN, i, t, (0.2, 0.3, 0.5, 1))
                           for i, t in enumerate(MAIN)]
        self.isr_slabs = [self._slab(X_ISR, i, t, (0.45, 0.2, 0.35, 1))
                          for i, t in enumerate(ISR)]
        self.pc = self.label("PC →", (0, -0.4, 0), 0.38, theme.ACCENT, align="right")

        # 中断请求指示灯
        self.irq = self.box((2.4, 0.4, 0.5), (X_ISR, 0, 0.0), (0.3, 0.1, 0.15, 1))
        self.irq_text = self.label("中断请求：无", (X_ISR, -0.4, 0.0), 0.3)

        # 栈
        self.label("栈 Stack（在 SRAM 里）", (X_STACK, 0, 4.8), 0.36, theme.TEXT)
        self.box((2.8, 0.6, 0.1), (X_STACK, 0, 0.9), (0.4, 0.4, 0.45, 1))
        self.stack_nodes = []

        # 按键与 LED
        self.button = parts.Button(self.root, (X_CLOCK, -1.2, -0.8), label="按键")
        self.led = parts.LED(self.root, (X_ISR + 2.5, -1.2, -0.8), label="LED")

        self.accept("space", self.press)
        self.accept_keys(["arrow_up", "="], self.change_speed, [1])
        self.accept_keys(["arrow_down", "-"], self.change_speed, [-1])
        self.set_body(INTRO)
        self.refresh()

    def _slab(self, x, i, text, color):
        z = SLAB_TOP - i * SLAB_STEP
        node = self.box((4.2, 0.4, 0.7), (x, 0, z), color)
        self.label(text, (x, -0.3, z - 0.1), 0.3)
        return node

    # ---------- 输入 ----------
    def press(self):
        self.pending = True
        self.press_t = 0.3
        self.button.set_pressed(True)
        self.refresh()

    def change_speed(self, d):
        self.speed_i = max(0, min(len(SPEEDS) - 1, self.speed_i + d))
        self.refresh()

    # ---------- 执行逻辑 ----------
    def clock_edge(self):
        """时钟上升沿：执行一条指令。"""
        if self.mode == "main":
            if self.pending:
                self.pending = False
                self.saved_idx = self.idx
                self.mode = "isr"
                self.idx = 0
                self.irq_count += 1
                self.push("返回：%s" % MAIN[self.saved_idx])
                self.push("寄存器备份")
            else:
                self.idx = (self.idx + 1) % len(MAIN)
        else:
            if self.idx == len(ISR) - 1:
                self.pop()
                self.pop()
                self.mode = "main"
                self.idx = self.saved_idx
            else:
                self.idx += 1
                if self.idx == 1:
                    self.led_on = not self.led_on
                    self.led.set_on(self.led_on)
        self.refresh()

    def push(self, text):
        z = 1.3 + len(self.stack_nodes) * 0.75
        node = self.box((2.6, 0.5, 0.65), (X_STACK, 0, z), (0.5, 0.5, 0.25, 1))
        self.label(text, (0, -0.35, -0.1), 0.26, parent=node)
        self.stack_nodes.append(node)

    def pop(self):
        if self.stack_nodes:
            self.stack_nodes.pop().removeNode()

    def refresh(self):
        slabs = self.main_slabs if self.mode == "main" else self.isr_slabs
        for s in self.main_slabs + self.isr_slabs:
            s.clearColorScale()
        cur = slabs[self.idx]
        cur.setColorScale(2.0, 2.0, 2.0, 1)
        x = X_MAIN if self.mode == "main" else X_ISR
        self.pc.setPos(x - 2.2, -0.4, SLAB_TOP - self.idx * SLAB_STEP - 0.1)
        if self.pending:
            self.irq.setColor(1.0, 0.2, 0.3, 1, 1)
            set_text(self.irq_text, "中断请求：有！")
        else:
            self.irq.clearColor()
            set_text(self.irq_text, "中断请求：无")
        hz = SPEEDS[self.speed_i]
        set_text(self.freq_text, "%g 拍/秒（演示）" % hz)
        state = ("正在执行主程序第 %d 条" % (self.idx + 1) if self.mode == "main"
                 else "正在处理中断（第 %d 次）" % self.irq_count)
        self.set_body(INTRO + "\n\n当前状态：%s" % state)

    def update(self, dt):
        if self.press_t > 0:
            self.press_t -= dt
            if self.press_t <= 0:
                self.button.set_pressed(False)
        half = 0.5 / SPEEDS[self.speed_i]
        self.half_t += dt
        while self.half_t >= half:
            self.half_t -= half
            self.level ^= 1
            self.levels = self.levels[1:] + [self.level]
            self.wave.set_levels(self.levels)
            if self.level == 1:
                self.clock_edge()
        if self.pending:
            k = 0.6 + 0.6 * parts.pulse(self.time, 12)
            self.irq.setColorScale(k + 0.4, k + 0.4, k + 0.4, 1)
        else:
            self.irq.clearColorScale()
