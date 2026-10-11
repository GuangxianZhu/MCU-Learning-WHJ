"""第 1 课：什么是 MCU。"""

from .. import log as applog
from .. import parts, theme
from ..schem.draw import ACTIVE, INK, Canvas
from .base import Lesson

STEPS = [
    ("MCU 是 Micro Controller Unit 的缩写，中文叫“微控制器”，"
     "也常被叫做“单片机”。\n\n"
     "一句话理解：MCU 就是把一台小电脑（大脑 + 记忆 + 手脚）"
     "全部做进了一颗芯片里。\n\n"
     "画面中间是一张“电路图”：用方块表示元件、用线表示导线，"
     "就是后面芯片内部模拟器的那种画法（和电路仿真软件 Logisim 一样）。\n\n"
     "中间这块黑色的大方块就是一颗 MCU，它焊在电路板（PCB）上，"
     "右边通过导线接着一个 LED 灯和一个按键。\n\n"
     "芯片里已经烧好了一个小程序：一直盯着按键，按键按下就点亮 LED。"
     "用鼠标左键点一下右上角的“按键”试试，再点一下就松开。"),
    ("看芯片两边一根根伸出来的小短线（正在闪），它们叫“引脚”（Pin），"
     "每根都有名字：PA0、PA5、VDD……\n\n"
     "引脚是 MCU 和外界交流的唯一通道：\n"
     "· 输出：让引脚变成高电压，LED 就亮了\n"
     "· 输入：读取引脚电压，就知道按键有没有被按下\n"
     "· 通信：用几根引脚和别的芯片“说话”\n\n"
     "电路图里的线，在真实电路板上就是一条条铜做的“走线”，把引脚连到 LED 和按键。\n\n"
     "线的颜色表示它现在的电压：亮绿是 1（高电压），深绿是 0（低电压）。"
     "点一下右边的按键试试，按下以后会发生三件事：\n"
     "① 按键把 PA0 接到 3.3V，PA0 那根线变成亮绿（输入 = 1）\n"
     "② 芯片里的程序读到 PA0 是 1，就让 PA5 输出 1，PA5 那根线也变亮绿\n"
     "③ 电流从 PA5 经过电阻流进 LED，LED 亮了\n"
     "注意按键和 LED 之间没有直接连线：是芯片里的程序把“输入”变成了“输出”。"),
    ("黑色外壳叫“封装”，作用是保护里面娇嫩的东西。\n\n"
     "我们把外壳揭开……里面是一小片灰色的硅片，叫“晶片”（Die）。"
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
     "看，现在换了一个程序，它不看按键，只是让 LED 一闪一闪：PA5 那根线变成亮绿表示"
     "引脚输出了高电压（1，灯亮），深绿表示低电压（0，灯灭）。\n\n"
     "这就是最经典的第一个单片机程序——“点灯”。恭喜你完成第 1 课！"),
]


PIN_LIGHT = (0.85, 0.85, 0.85, 1)
PKG = (0.13, 0.13, 0.15, 1)
DIE = (0.8, 0.81, 0.84, 1)
RIGHT_PINS = ["PA0", "PA1", "PA2", "PA3", "PA4", "PA5", "PA6", "PA7"]
LEFT_PINS = ["VDD 3.3V", "GND 地", "NRST 复位", "BOOT0", "OSC_IN", "OSC_OUT", "PB0", "PB1"]
LED_ON = (1.0, 0.15, 0.1, 1)
LED_OFF = (0.35, 0.08, 0.08, 1)


def _pin_z(k):
    return 19 - 2 * k


class WhatIsMCU(Lesson):
    title = "什么是 MCU"
    summary = "一台缩进芯片里的小电脑"
    hints = "空格 下一步   退格 上一步   左键点芯片 打开/合上外壳   左键点按键 按下/松开（按下 LED 亮）"
    view2d = True
    bounds = (-4, -1, 43, 25)
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
        self.blink_t = 0.0
        self.pressed = False
        self.led_on = False
        self.note = ""
        c = self.canvas = Canvas(self)
        x0, z0, x1, z1 = self.bounds
        c.paper(x0, z0, x1, z1)
        c.text("一块电路板的电路图：MCU、LED、按键", -3.5, 23.6, 0.8)

        # 芯片：黑色封装 + 两边的引脚
        self.pkg = c.box(8, 3, 20, 21, "", tag="chip", fill=PKG)
        self.pkg_text = c.text("MCU", 14, 11.2, 2.2, PIN_LIGHT, "center")
        self.pin_shapes = []
        self.pin_labels = []
        for k, name in enumerate(RIGHT_PINS):
            z = _pin_z(k)
            self.pin_shapes.append(c.box(20, z - 0.22, 21.2, z + 0.22, "", fill=INK))
            self.pin_labels.append(c.text(name, 19.7, z - 0.22, 0.55, PIN_LIGHT, "right"))
        for k, name in enumerate(LEFT_PINS):
            z = _pin_z(k)
            self.pin_shapes.append(c.box(6.8, z - 0.22, 8, z + 0.22, "", fill=INK))
            self.pin_labels.append(c.text(name.split()[0], 8.3, z - 0.22, 0.55, PIN_LIGHT))
            if " " in name:
                c.text(name.split()[1], 6.5, z - 0.22, 0.5, INK, "right")

        # 揭开外壳后看到的晶片和里面的几块区域
        self.inner = Canvas(self)
        ic = self.inner
        ic.text("晶片 Die", 14, 20.0, 0.6, INK, "center")
        for (bx0, bz0, bx1, bz1, color, name) in [
                (9.6, 11.8, 13.7, 19.4, theme.CPU, "CPU\n大脑"),
                (14.3, 11.8, 18.4, 19.4, theme.FLASH, "Flash\n存程序"),
                (9.6, 4.4, 13.7, 11.2, theme.SRAM, "SRAM\n存数据"),
                (14.3, 4.4, 18.4, 11.2, theme.GPIO, "外设\n手和眼睛")]:
            ic.box(bx0, bz0, bx1, bz1, "", fill=color)
            ic.text(name, (bx0 + bx1) / 2, (bz0 + bz1) / 2 + 0.2, 0.75, (1, 1, 1, 1), "center")
        self.inner.root.setY(-0.08)   # 盖在封装前面
        self.inner.root.hide()

        # LED：PA5 → 限流电阻 → LED → 地
        z = _pin_z(5)
        self.led_wire = [c.wire([(21.2, z), (25, z)]), c.wire([(28, z), (31.1, z)])]
        c.box(25, z - 0.5, 28, z + 0.5, "", tag="res")
        c.text("220Ω 电阻", 26.5, z + 0.8, 0.5, INK, "center")
        self.led = c.box(31.1, z - 1, 33.1, z + 1, "", tag="led", fill=LED_OFF)
        c.text("LED", 32.1, z + 1.3, 0.6, INK, "center")
        c.line([(33.1, z), (35, z), (35, z - 2.5)], INK, 0.12)
        self._ground(35, z - 2.5)

        # 按键：按下时把 PA0 接到 3.3V
        z = _pin_z(0)
        self.btn_wire = c.wire([(21.2, z), (31, z)])
        self.btn = c.box(31, z - 1, 33, z + 1, "", tag="button")
        c.text("按键", 32, z + 1.3, 0.6, INK, "center")
        c.line([(33, z), (35, z), (35, z + 2.5)], INK, 0.12)
        c.text("3.3V", 35, z + 2.8, 0.55, INK, "center")
        c.text("（点一下按下 / 再点松开）", 32, z - 1.9, 0.45, INK, "center")
        # 电路图右下角直接写出芯片里的程序在做什么，不用去翻左边的讲解
        self.prog_text = c.text("", 23, 3.6, 0.7, INK)

        self.accept("space", self.next_step)
        self.accept("backspace", self.prev_step)
        self.show_step()
        self.refresh()

    def home(self):
        self.app.fit_view(*self.bounds)

    def _ground(self, x, z):
        c = self.canvas
        for k, half in enumerate((0.9, 0.6, 0.3)):
            c.line([(x - half, z - 0.35 * k), (x + half, z - 0.35 * k)], INK, 0.1)
        c.text("地 GND", x + 1.2, z - 0.6, 0.5, INK)

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
        applog.log.debug("第 1 课：第 %d 步", i + 1)
        self.note = ""
        self.lid_open = i in (2, 3, 4)
        self.show_text()
        if i == 0:
            self.home()
        self.refresh()

    def show_text(self):
        i = self.step_i
        nav = "\n\n（第 %d / %d 步，按空格继续）" % (i + 1, len(STEPS))
        self.set_body(STEPS[i] + ("\n\n" + self.note if self.note else "") + nav)

    def on_pick(self, tag):
        if tag == "chip":
            self.lid_open = not self.lid_open
            self.refresh()
        elif tag == "button":
            self.pressed = not self.pressed
            if self.step_i == 5:
                self.note = ("现在跑的是闪灯程序，它不读按键，所以按键不影响 LED。"
                             "按退格回到前面几步，按键就又能控制 LED 了。")
            else:
                self.note = ("按键%s：PA0 = %d → 程序让 PA5 = %d → LED %s。"
                             % (("按下", 1, 1, "亮") if self.pressed else ("松开", 0, 0, "灭")))
            self.show_text()
            self.refresh()
        elif tag == "led":
            self.note = ("LED 本身不能点，它只听 PA5 的：点右上角的“按键”让程序点亮它，"
                         "或者一直按空格到第 6 步看它自己闪。")
            self.show_text()

    def refresh(self):
        open_ = self.lid_open
        self.pkg.set_fill(DIE if open_ else PKG)
        if open_:
            self.inner.root.show()
            self.pkg_text.hide()
        else:
            self.inner.root.hide()
            self.pkg_text.show()
        for t in self.pin_labels:
            t.node().setTextColor(*(INK if open_ else PIN_LIGHT))
        self.btn_wire.set(int(self.pressed))
        self.btn.set_fill(ACTIVE if self.pressed else (1, 1, 1, 1))
        if self.step_i != 5:
            # 前几步芯片里的程序是：PA5 = PA0（按键按下就点灯）
            self.set_led(self.pressed)
        if self.step_i != 1:
            for p in self.pin_shapes:
                p.set_fill(INK)

    def update(self, dt):
        if self.step_i == 1:
            on = parts.pulse(self.time, 3) > 0.5
            for p in self.pin_shapes:
                p.set_fill(ACTIVE if on else INK)
        if self.step_i == 5:
            self.blink_t += dt
            self.set_led((self.blink_t % 1.0) < 0.5, quiet=True)

    def set_led(self, on, quiet=False):
        on = bool(on)
        if on != self.led_on and not quiet:
            applog.log.info("第 1 课：LED %s（PA0=%d PA5=%d）", "亮" if on else "灭",
                            int(self.pressed), int(on))
        self.led_on = on
        for w in self.led_wire:
            w.set(int(on))
        self.led.set_fill(LED_ON if on else LED_OFF)
        if self.step_i == 5:
            prog = "芯片里的程序：让 PA5 每 0.5 秒翻转一次\n（这个程序不看按键）"
        else:
            prog = ("芯片里的程序：一直读 PA0，把读到的值写给 PA5\n现在 PA0=%d → PA5=%d → LED %s"
                    % (int(self.pressed), int(on), "亮" if on else "灭"))
        self.prog_text.node().setText(prog)
