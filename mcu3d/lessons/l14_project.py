"""第 14 课：综合项目——温度报警器。"""

from .. import parts, shapes, theme
from ..ui import set_text, text3d
from .base import Lesson

CHIP = (0.0, 0.0, 0)
SENSOR = (-7.0, 0.5, 0)
PC_POS = (8.8, 3.6, 0)
TICK = 1.2              # 演示里“每 0.5 秒”放慢成 1.2 秒一轮
STEP_T = 0.16           # 流程里每一步高亮的时间
V_PER_C = 0.05          # 假设：温度每升高 1℃，传感器电压升高 0.05V
FLOW = ["定时器中断\n（每 0.5 秒）", "ADC\n读电压", "换算\n成温度", "和阈值\n比较",
        "控制 LED\n和蜂鸣器", "串口发送\n给电脑"]

CODE = (
    "volatile int flag = 0;\n"
    "void TIM2_IRQHandler(void) {   // 定时器中断，每 0.5 秒一次\n"
    "    flag = 1;\n"
    "}\n"
    "int main(void) {\n"
    "    init_all();   // 开时钟，配置 GPIO/ADC/TIM/UART\n"
    "    while (1) {\n"
    "        if (flag) {\n"
    "            flag = 0;\n"
    "            int code = adc_read();          // 0~4095\n"
    "            float v = code * 3.3f / 4095;   // 换成电压\n"
    "            float t = v / 0.05f;            // 换成温度\n"
    "            if (t > LIMIT) { red_on(); buzzer(50); }\n"
    "            else           { green_on(); buzzer(0); }\n"
    "            printf(\"T=%.1fC\\r\\n\", t);   // 经 UART 发出\n"
    "        }\n"
    "    }\n"
    "}")

INTRO = (
    "把前面学过的都用上，做一个温度报警器：温度超过“阈值”（设定的分界线）"
    "就亮红灯、蜂鸣器响，平时亮绿灯，并且把温度通过串口发给电脑。\n\n"
    "每一轮的流程（画面后排的 6 个方块会依次亮起）：\n"
    "① 定时器每 0.5 秒产生一次更新事件 → 定时器中断（第 6、5 课）\n"
    "② 用 ADC 读温度传感器的电压（第 13 课）\n"
    "③ CPU 把读数换算成温度：电压 = 读数 ÷ 4095 × 3.3V，温度 = 电压 ÷ 0.05V\n"
    "④ 和阈值比较\n"
    "⑤ 写 GPIO 的 ODR 控制两个 LED（第 8 课），用定时器的 PWM 驱动蜂鸣器（第 9 课）\n"
    "⑥ 用 UART 把“T=25.0C”发给电脑（第 11 课）\n\n"
    "为什么用定时器中断而不是 delay？因为中断让测量间隔非常准，"
    "而且等待的时候 CPU 还能做别的事。")


class ProjectLesson(Lesson):
    title = "综合项目：温度报警器"
    summary = "做一个温度报警器"
    hints = "按住 H 给传感器加热（松开慢慢变凉）   上下方向键 调整报警阈值"
    camera = (40, 0, -45, (0.0, 1.2, 0.8))
    location = ["all", "bus", "pins"]
    location_text = (
        "几乎整颗芯片都用上了：定时器（定时 + PWM）、NVIC（定时器中断）、ADC（读温度）、"
        "CPU 与 SRAM（计算、存变量）、GPIO（LED）、UART（发给电脑），"
        "程序本身存在 Flash 里。")
    link_text = (
        "这一课把前面的都用上：GPIO（第 8 课）、定时器和 PWM（第 9 课）、中断（第 10 课）、UART（第 11 课）、ADC（第 13 课），“温度超过阈值”用的是第 6 课的比较和条件跳转。")
    apply_text = (
        "能在 Wokwi 网页上仿真，或用一块 STM32 蓝色小板（几十元）做出真的温度报警器；再改成湿度计、光控灯、自动浇花器也是同一个套路。")
    sim_program = "alarm"
    terms = ["传感器", "热敏电阻", "阈值", "蜂鸣器"]

    def setup(self):
        self.temp = 24.0
        self.heating = False
        self.limit = 30
        self.tick_t = TICK - 0.3
        self.step = None
        self.step_t = 0.0
        self.code = 0
        self.measured = None
        self.alarm = False
        self.log = []

        self.box((24, 13, 0.2), (0.5, 0.8, -0.1), theme.PCB)
        self.chip = parts.Chip(self.root, size=4, pos=CHIP, label="MCU")

        # 温度传感器 + 温度计
        self.sensor = self.box((0.9, 0.9, 0.9), (SENSOR[0], SENSOR[1], 0.45),
                               (0.15, 0.15, 0.18, 1))
        self.heat_glow = shapes.cylinder(1.0, 1.6, (1.0, 0.35, 0.1, 1))
        self.heat_glow.reparentTo(self.root)
        self.heat_glow.setPos(SENSOR[0], SENSOR[1], 0)
        self.heat_glow.setLightOff(1)
        self.heat_glow.setDepthWrite(False)
        shapes.make_transparent(self.heat_glow, 0)
        self.label("温度传感器\n（热敏电阻）", (SENSOR[0], SENSOR[1], 1.9), 0.3)
        self.thermo_bar = self.box((0.5, 0.5, 1.0), (-9.6, 0.5, 0), (1.0, 0.3, 0.2, 1))
        frame = self.box((0.7, 0.7, 5.0), (-9.6, 0.5, 2.5), (0.7, 0.8, 0.9, 1))
        shapes.make_transparent(frame, 0.15)
        frame.setDepthWrite(False)
        self.temp_text = self.label("", (-9.6, 0.5, 5.7), 0.38, theme.ACCENT)
        self.limit_mark = self.box((1.1, 1.1, 0.05), (-9.6, 0.5, 0), (1, 1, 1, 1))
        self.limit_text = self.label("", (-8.9, 0.5, 0), 0.26, align="left")
        px, py, _ = self.chip.pin_pos(2, 4)
        self.wire([(SENSOR[0] + 0.45, SENSOR[1], 0.2), (px, py, 0.2)], theme.ADC, 4)
        self.label("ADC 引脚", (-4.2, 1.0, 0.3), 0.24, theme.TEXT_DIM)

        # 输出：两个 LED 和蜂鸣器
        self.led_g = parts.LED(self.root, (5.2, 1.0, 0), theme.LED_GREEN, label="绿灯 正常")
        self.led_r = parts.LED(self.root, (5.2, -1.2, 0), theme.LED_RED, label="红灯 报警")
        for k, y in ((6, 1.0), (4, -1.2)):
            x0, y0, _ = self.chip.pin_pos(0, k)
            self.wire([(x0, y0, 0.2), (3.5, y0, 0.2), (3.5, y, 0.2), (4.8, y, 0.2)],
                      theme.GPIO, 3)
        self.buzzer = shapes.cylinder(0.6, 0.6, (0.1, 0.1, 0.1, 1))
        self.buzzer.reparentTo(self.root)
        self.buzzer.setPos(5.2, -3.6, 0)
        self.label("蜂鸣器（PWM）", (5.2, -3.6, 1.3), 0.28, theme.TEXT_DIM)
        self.beep_text = self.label("", (6.6, -3.6, 1.2), 0.42, theme.LED_RED)
        x0, y0, _ = self.chip.pin_pos(3, 6)
        self.wire([(x0, y0, 0.2), (x0, -3.6, 0.2), (4.6, -3.6, 0.2)], theme.TIMER, 3)

        # 电脑（串口终端）
        self.box((4.2, 0.3, 2.8), (PC_POS[0], PC_POS[1], 1.6), (0.15, 0.15, 0.17, 1))
        self.box((3.9, 0.05, 2.5), (PC_POS[0], PC_POS[1] - 0.17, 1.6), (0.02, 0.05, 0.03, 1))
        self.box((0.4, 0.4, 0.3), (PC_POS[0], PC_POS[1], 0.15), (0.3, 0.3, 0.32, 1))
        self.label("电脑（串口助手）", (PC_POS[0], PC_POS[1], 3.4), 0.3, theme.TEXT_DIM)
        self.screen = text3d("", self.root, (PC_POS[0] - 1.8, PC_POS[1] - 0.25, 2.55),
                             0.26, theme.LED_GREEN, align="left", billboard=False)
        ux, uy, _ = self.chip.pin_pos(1, 6)
        self.uart_path = [(ux, uy, 0.5), (ux, PC_POS[1] - 1.2, 0.5),
                          (PC_POS[0], PC_POS[1] - 1.2, 0.5), (PC_POS[0], PC_POS[1] - 0.3, 0.5)]
        self.wire([(p[0], p[1], 0.2) for p in self.uart_path], theme.UART, 3)
        self.label("UART TX", (ux + 0.3, uy + 1.5, 0.3), 0.24, theme.TEXT_DIM, align="left")

        # 程序流程
        self.flow = []
        for i, name in enumerate(FLOW):
            x = -6.5 + i * 2.5
            node = self.box((2.2, 0.6, 1.0), (x, 6.3, 0.5), (0.2, 0.25, 0.4, 1))
            self.label(name, (x, 5.9, 1.4), 0.24)
            self.flow.append(node)
        self.label("程序每一轮做的事 →", (-6.5, 7.2, 0.4), 0.28, theme.ACCENT, align="left")

        self.accept("h", self.set_heat, [True])
        self.accept("h-up", self.set_heat, [False])
        self.accept_keys(["arrow_up"], self.change_limit, [1])
        self.accept_keys(["arrow_down"], self.change_limit, [-1])
        self.apply_outputs()
        self.refresh()

    # ---------- 输入 ----------
    def set_heat(self, on):
        self.heating = on

    def change_limit(self, d):
        self.limit = max(20, min(45, self.limit + d))
        self.refresh()

    # ---------- 程序的一轮 ----------
    def run_step(self, i):
        for k, node in enumerate(self.flow):
            if k == i:
                node.setColorScale(2.2, 2.2, 2.2, 1)
            else:
                node.clearColorScale()
        if i == 1:
            v = self.temp * V_PER_C
            self.code = int(round(v / 3.3 * 4095))
            px, py, _ = self.chip.pin_pos(2, 4)
            self.movers.append(parts.Packet(
                self.root, [(SENSOR[0] + 0.5, SENSOR[1], 0.6), (px, py, 0.6)],
                theme.ADC, speed=14, size=0.35, label="%.2fV" % v))
        elif i == 2:
            self.measured = self.code * 3.3 / 4095 / V_PER_C
        elif i == 3:
            self.alarm = self.measured > self.limit
        elif i == 4:
            self.apply_outputs()
        elif i == 5:
            line = "T=%.1fC%s" % (self.measured, "  ALARM!" if self.alarm else "")
            self.movers.append(parts.Packet(
                self.root, self.uart_path, theme.UART, speed=16, size=0.35,
                label="T=%.1f" % self.measured, on_done=lambda: self.print_line(line)))
            self.refresh()

    def print_line(self, line):
        self.log = (self.log + [line])[-7:]
        set_text(self.screen, "\n".join(self.log))

    def apply_outputs(self):
        self.led_g.set_on(not self.alarm)
        if not self.alarm:
            self.led_r.set_on(False)
            set_text(self.beep_text, "")
            self.buzzer.setScale(1)

    def refresh(self):
        if self.measured is None:
            state = "等待第一次测量……"
        else:
            state = ("ADC 读数 %d → 电压 %.2fV → 温度 %.1f℃，阈值 %d℃，%s"
                     % (self.code, self.code * 3.3 / 4095, self.measured, self.limit,
                        "超过阈值：报警！" if self.alarm else "正常"))
        self.set_body(INTRO + "\n\n【现在】" + state +
                      "\n\n【完整程序（C 语言，简化版）】\n" + CODE)

    # ---------- 每帧 ----------
    def update(self, dt):
        target = 46.0 if self.heating else 24.0
        self.temp += (target - self.temp) * min(1.0, dt * (0.5 if self.heating else 0.25))
        h = 5.0 * self.temp / 50.0
        self.thermo_bar.setSz(h)
        self.thermo_bar.setZ(h / 2)
        set_text(self.temp_text, "%.1f℃" % self.temp)
        lz = 5.0 * self.limit / 50.0
        self.limit_mark.setZ(lz)
        self.limit_text.setZ(lz - 0.1)
        set_text(self.limit_text, "阈值 %d℃" % self.limit)
        self.heat_glow.setAlphaScale(0.35 if self.heating else 0.0)

        self.tick_t += dt
        if self.tick_t >= TICK:
            self.tick_t -= TICK
            self.step = 0
            self.step_t = 0.0
            self.run_step(0)
        elif self.step is not None:
            self.step_t += dt
            if self.step_t >= STEP_T:
                self.step_t = 0.0
                self.step += 1
                if self.step < len(FLOW):
                    self.run_step(self.step)
                else:
                    self.step = None
                    for node in self.flow:
                        node.clearColorScale()

        if self.alarm:
            on = (self.time * 4) % 1.0 < 0.5
            self.led_r.set_on(on)
            set_text(self.beep_text, "嘀！" if on else "")
            self.buzzer.setScale(1.15 if on else 1.0)
