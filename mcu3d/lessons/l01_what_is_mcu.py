"""第 1 课：什么是 MCU。"""

from .. import parts, shapes, theme
from .base import Lesson

STEPS = [
    ("MCU 是 Micro Controller Unit 的缩写，中文叫“微控制器”，"
     "也常被叫做“单片机”。\n\n"
     "一句话理解：MCU 就是把一台小电脑（大脑 + 记忆 + 手脚）"
     "全部做进了一颗芯片里。\n\n"
     "画面中间这块黑色的方块就是一颗 MCU，它焊在绿色的电路板（PCB）上，"
     "旁边有一个 LED 灯和一个按键。"),
    ("看芯片四周一圈亮晶晶的金属脚，它们叫“引脚”（Pin）。\n\n"
     "引脚是 MCU 和外界交流的唯一通道：\n"
     "· 输出：让引脚变成高电压，LED 就亮了\n"
     "· 输入：读取引脚电压，就知道按键有没有被按下\n"
     "· 通信：用几根引脚和别的芯片“说话”\n\n"
     "电路板上金黄色的线叫“走线”，把引脚连到 LED 和按键。"),
    ("黑色外壳叫“封装”，作用是保护里面娇嫩的东西。\n\n"
     "我们把外壳揭开……里面是一小片银色的硅片，叫“晶片”（Die）。"
     "真实的晶片只有指甲盖大小，上面有几百万个晶体管。\n\n"
     "（也可以随时用鼠标左键点击芯片来打开/合上外壳）"),
    ("硅片上分成了几个区域，每个都有自己的工作：\n\n"
     "· CPU 内核（红）：大脑，负责一条条执行程序\n"
     "· Flash（蓝）：存放程序，断电也不会丢\n"
     "· SRAM（绿）：存放运行时的临时数据，断电就丢\n"
     "· 外设（橙）：GPIO、定时器、串口……是 MCU 的“手和眼睛”\n\n"
     "按 S 打开芯片内部模拟器，可以点开每个模块看介绍；第 3 课起会把它们一块块放大细看。"),
    ("MCU 和电脑有什么不一样？\n\n"
     "电脑 CPU：几 GHz，内存几十 GB，要先运行操作系统，几百上千元。\n"
     "MCU：几十到几百 MHz，内存只有几 KB 到几百 KB，"
     "直接运行你写的程序，几毛钱到几十块，非常省电。\n\n"
     "MCU 藏在生活的各个角落：遥控器、洗衣机、电动牙刷、智能手环、"
     "键盘鼠标……一辆汽车里就有几十上百颗。"),
    ("MCU 一生都在重复同一件事：\n\n"
     "0. 事先：你在电脑上用 C 语言写程序，编译成机器码，再烧录（下载）进 Flash\n"
     "1. 上电后，CPU 从 Flash 里读出程序\n"
     "2. 一条一条地执行指令\n"
     "3. 通过引脚控制外面的东西\n\n"
     "看，现在芯片里的程序正在让 LED 一闪一闪：走线变成橙色表示"
     "引脚输出了高电压（亮），蓝色表示低电压（灭）。\n\n"
     "这就是最经典的第一个单片机程序——“点灯”。恭喜你完成第 1 课！"),
]


class WhatIsMCU(Lesson):
    title = "什么是 MCU"
    summary = "一台缩进芯片里的小电脑"
    hints = "空格 下一步   退格 上一步   左键点芯片 打开/合上外壳"
    camera = (27, 15, -40, (1.0, 0, 0))
    location = ["all", "pins"]
    location_text = "整颗芯片。这一课先从外面看 MCU 长什么样，再揭开外壳看看里面有哪些部分。"
    link_text = (
        "这是第一课。后面 13 课会各自放大这颗芯片的一块：第 2 课学数据怎么用 0 和 1 表示，第 3–7 课钻进 CPU 和存储器，第 8–13 课学外设，第 14 课把它们合成一个温度报警器。")
    apply_text = (
        "看到一块电路板，能认出哪颗是 MCU、哪些是引脚和走线；知道“写程序 → 编译 → 烧录 → 运行”这条流程。")
    sim_program = "inc"
    terms = ["MCU", "芯片", "PCB", "走线", "引脚", "LED", "电压", "封装", "晶片",
             "晶体管", "CPU", "Flash", "SRAM", "外设", "程序", "编译", "烧录"]

    def setup(self):
        self.step_i = 0
        self.lid_open = False
        self.lid_t = 0.0
        self.blink_t = 0.0

        self.box((15, 10, 0.3), (0, 0, -0.15), theme.PCB)

        # 芯片内部：硅片和功能区（先做，外壳盖在上面）
        self.die = self.root.attachNewNode("die")
        self.box((3.2, 3.2, 0.1), (0, 0, 0.3), theme.DIE, parent=self.die)
        self.blocks = self.root.attachNewNode("blocks")
        for (x, y, w, h, color, name) in [
                (-0.75, 0.75, 1.3, 1.3, theme.CPU, "CPU"),
                (0.75, 0.75, 1.3, 1.3, theme.FLASH, "Flash"),
                (-0.75, -0.75, 1.3, 1.3, theme.SRAM, "SRAM"),
                (0.75, -0.75, 1.3, 1.3, theme.GPIO, "外设")]:
            self.box((w, h, 0.15), (x, y, 0.42), color, parent=self.blocks)
            self.label(name, (x, y, 0.9), 0.32, parent=self.blocks)
        self.blocks.hide()

        self.chip = parts.Chip(self.root, size=4, height=0.7, label=None)
        self.chip.body.removeNode()
        # 外壳单独做成可以掀开的盖子
        self.lid = shapes.box((4, 4, 0.7), theme.CHIP, "lid")
        self.lid.reparentTo(self.root)
        self.lid.setZ(0.4)
        self.lid_text = self.label("MCU", (0, 0, 0.36), 0.7,
                                   (0.8, 0.8, 0.8, 1), parent=self.lid,
                                   billboard=False)
        self.lid_text.setP(-90)
        self.make_pickable(self.lid, "chip")

        # LED 与按键，以及走线
        self.led = parts.LED(self.root, (5, 2, 0), label="LED")
        self.button = parts.Button(self.root, (5, -2.5, 0), label="按键")
        p_led = self.chip.pin_pos(0, 6)
        p_btn = self.chip.pin_pos(0, 1)
        self.trace_led = self.root.attachNewNode("trace-led")
        for a, b in [(p_led, (3.5, p_led[1], 0.02)),
                     ((3.5, p_led[1], 0.02), (3.5, 2, 0.02)),
                     ((3.5, 2, 0.02), (4.6, 2, 0.02))]:
            shapes.flat_trace(a[:2] + (0.02,), b, color=theme.COPPER).reparentTo(
                self.trace_led)
        for a, b in [(p_btn, (3.5, p_btn[1], 0.02)),
                     ((3.5, p_btn[1], 0.02), (3.5, -2.5, 0.02)),
                     ((3.5, -2.5, 0.02), (4.4, -2.5, 0.02))]:
            shapes.flat_trace(a[:2] + (0.02,), b, color=theme.COPPER).reparentTo(
                self.root)

        self.label("电路板 PCB", (-5.5, -4, 0.3), 0.4, theme.TEXT_DIM)

        self.accept("space", self.next_step)
        self.accept("backspace", self.prev_step)
        self.show_step()

    def next_step(self):
        if self.step_i < len(STEPS) - 1:
            self.step_i += 1
            self.show_step()

    def prev_step(self):
        if self.step_i > 0:
            self.step_i -= 1
            self.show_step()

    def show_step(self):
        i = self.step_i
        text = STEPS[i]
        nav = "\n\n（第 %d / %d 步，按空格继续）" % (i + 1, len(STEPS))
        self.set_body(text + nav)
        self.lid_open = i in (2, 3, 4)
        if i != 5:
            self.led.set_on(False)
            self.trace_led.clearColor()
        if i != 1:
            for pin in self.chip.pins:
                pin.clearColorScale()

    def on_pick(self, tag):
        if tag == "chip":
            self.lid_open = not self.lid_open

    def update(self, dt):
        # 盖子平滑打开/合上
        target = 1.0 if self.lid_open else 0.0
        self.lid_t += (target - self.lid_t) * min(1.0, dt * 4)
        self.lid.setZ(0.4 + self.lid_t * 3.0)
        self.lid.setR(self.lid_t * 25)
        self.blocks.show() if self.lid_t > 0.3 else self.blocks.hide()
        if self.lid_t > 0.02:
            shapes.make_transparent(self.lid, 1.0 - 0.75 * self.lid_t)
        else:
            self.lid.clearTransparency()
            self.lid.setAlphaScale(1)

        if self.step_i == 1:
            k = 1 + 1.5 * parts.pulse(self.time, 6)
            for pin in self.chip.pins:
                pin.setColorScale(k, k, k * 0.6, 1)

        if self.step_i == 5:
            self.blink_t += dt
            on = (self.blink_t % 1.0) < 0.5
            self.led.set_on(on)
            c = theme.HIGH if on else theme.LOW
            self.trace_led.setColor(c[0], c[1], c[2], 1, 1)
