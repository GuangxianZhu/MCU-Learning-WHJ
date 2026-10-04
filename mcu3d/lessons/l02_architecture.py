"""第 2 课：MCU 内部构造——CPU、存储器、外设和总线。"""

from .. import parts, theme
from .base import Lesson

BUS_Y = 0.0
BLOCK_Z = 0.45
TOP_Y = 2.9
BOT_Y = -2.9

# (标识, 名称, 颜色, x, y, 介绍)
BLOCKS = [
    ("cpu", "CPU\n内核", theme.CPU, -5.6, TOP_Y,
     "CPU 内核：MCU 的“大脑”。\n\n"
     "它只会做非常简单的事：取一条指令 → 看懂它 → 执行它，然后取下一条。"
     "但它做得极快，每秒几千万次。\n\n"
     "CPU 里有一个叫 PC（程序计数器）的小格子，记着“下一条指令在哪”。"
     "还有十几个“寄存器”用来临时放正在计算的数。"),
    ("nvic", "中断\n控制器", theme.NVIC, -2.8, TOP_Y,
     "中断控制器（NVIC）：MCU 的“门铃管家”。\n\n"
     "当按键被按下、数据到达、定时时间到……外设会“按门铃”。"
     "中断控制器负责通知 CPU 先放下手头的事，去处理这件急事，"
     "处理完再回来接着干。第 5 课会详细演示。"),
    ("flash", "Flash\n程序存储", theme.FLASH, 0.0, TOP_Y,
     "Flash：存放程序的地方，像一本“操作手册”。\n\n"
     "你在电脑上写好程序，编译后“烧录”进 Flash。断电后内容不会丢，"
     "所以单片机每次上电都能从头执行同一个程序。\n\n"
     "常见容量：16KB ~ 2MB。"),
    ("sram", "SRAM\n数据存储", theme.SRAM, 2.8, TOP_Y,
     "SRAM：存放运行时数据的“草稿纸”。\n\n"
     "程序里的变量（比如计数值、温度值）都放在这里。读写非常快，"
     "但一断电内容就全没了。\n\n"
     "常见容量：2KB ~ 512KB，比电脑内存小一百万倍！"),
    ("clock", "时钟\nRCC", theme.CLOCK, 5.6, TOP_Y,
     "时钟：MCU 的“心跳 / 节拍器”。\n\n"
     "它不停地发出“滴答”脉冲，CPU 和所有外设都跟着这个节拍工作。"
     "节拍越快（频率越高），执行越快，但也越耗电。\n\n"
     "例如 72MHz 表示每秒 7200 万次滴答。"),
    ("gpio", "GPIO\n通用输入输出", theme.GPIO, -5.6, BOT_Y,
     "GPIO：通用输入输出口，最基础的“手和眼睛”。\n\n"
     "每个引脚可以设成输出（控制 LED、继电器）或者输入（读取按键、开关）。"
     "第 4 课专门讲它。"),
    ("tim", "定时器\nTIM", theme.TIMER, -2.8, BOT_Y,
     "定时器：一个会自己数数的“秒表”。\n\n"
     "它跟着时钟一下一下地加 1，数到设定值就报告一次。"
     "可以用来精确延时、定时闪灯，还能输出 PWM 控制亮度和电机速度。第 6 课讲。"),
    ("uart", "UART\n串口", theme.UART, 0.0, BOT_Y,
     "UART 串口：让两块芯片“发短信”的外设。\n\n"
     "只用两根线（发送 TX、接收 RX），一位一位地把数据送出去。"
     "单片机和电脑通信、打印调试信息，最常用的就是它。第 7 课讲。"),
    ("i2c", "I2C / SPI", theme.I2C_SPI, 2.8, BOT_Y,
     "I2C 和 SPI：另外两种通信方式，用来连接传感器、屏幕、存储芯片等。\n\n"
     "I2C 只要两根线就能挂很多设备；SPI 线多一些但速度更快。"
     "后续课程会讲到。"),
    ("adc", "ADC\n模数转换", theme.ADC, 5.6, BOT_Y,
     "ADC：把“连续变化的电压”变成数字。\n\n"
     "比如温度传感器输出 0~3.3V 的电压，ADC 把它变成 0~4095 的数字，"
     "CPU 就能计算出温度了。"),
]

ADDRESS = {
    "cpu": "CPU 自己内部的寄存器（R0~R12、PC 等）没有地址，只有 CPU 自己能直接用。",
    "flash": "地址范围（以常见的 STM32F103 为例）：0x0800 0000 开始。",
    "sram": "地址范围（STM32F103）：0x2000 0000 开始。程序的变量和“栈”都在这里。",
    "gpio": "GPIOA 的寄存器从地址 0x4001 0800 开始，GPIOB 从 0x4001 0C00 开始。",
    "tim": "TIM2 的寄存器从地址 0x4000 0000 开始。",
    "uart": "USART1 的寄存器从地址 0x4001 3800 开始。",
    "i2c": "I2C1 的寄存器从地址 0x4000 5400 开始，SPI1 从 0x4001 3000 开始。",
    "adc": "ADC1 的寄存器从地址 0x4001 2400 开始。",
    "clock": "RCC（时钟控制）的寄存器从地址 0x4002 1000 开始。用之前要先在这里打开外设的时钟。",
    "nvic": "NVIC 的寄存器在 0xE000 E100 开始，紧挨着 CPU 内核。",
}

INTRO = ("现在我们把芯片里的硅片放大来看。\n\n"
         "上排是“核心”：CPU、中断控制器、两种存储器、时钟。\n"
         "下排是“外设”：MCU 用来和外界打交道的各种功能模块。\n\n"
         "中间那条长长的通道叫“总线”（Bus），所有模块都挂在上面，"
         "数据就在总线上跑来跑去，就像城市里的主干道。\n\n"
         "总线上每个模块都有自己的“地址”（门牌号）范围。以常见的 STM32F103 为例："
         "Flash 从 0x0800 0000 开始，SRAM 从 0x2000 0000 开始，"
         "所有外设的寄存器从 0x4000 0000 开始。CPU 想读写谁，就在总线上给出谁的地址"
         "——这叫“内存映射”。所以“寄存器在哪”的答案是：外设寄存器长在各自的外设里，"
         "但 CPU 用地址来找到它们。\n\n"
         "▶ 鼠标移到模块上会浮起，左键点击查看介绍。\n"
         "▶ 按空格，观看 CPU 执行一条“点灯”指令的全过程。")

DEMO = [
    ("flash", "cpu", theme.FLASH, "指令",
     "① 取指令：CPU 根据 PC 指向的地址，从 Flash 里取出下一条指令，"
     "经过总线送到 CPU。"),
    ("cpu", None, None, None,
     "② 译码与执行：CPU 看懂这条指令——“把数字 1 写到 GPIO 的输出寄存器”。"),
    ("cpu", "sram", theme.SRAM, "数据",
     "③ 记录变量：程序顺便把“灯的状态 = 亮”记到 SRAM 里的一个变量。"),
    ("cpu", "gpio", theme.GPIO, "写1",
     "④ 控制外设：CPU 经总线把 1 写进 GPIO 寄存器，对应引脚变成高电压，"
     "外面的 LED 亮了！"),
]


class Architecture(Lesson):
    title = "内部构造"
    summary = "CPU、存储器、外设和总线"
    hints = "鼠标悬停 浮起模块   左键 查看介绍   空格 演示一条指令"
    camera = (31, 0, -55, (0, -0.8, 0))
    location = ["all", "bus"]
    location_text = ("芯片内部那片硅晶片的全貌：所有模块，以及把它们连在一起的总线。"
                     "后面每一课都会单独放大其中一块，右上角的芯片地图会告诉你在哪。")
    terms = ["内核", "指令", "PC", "寄存器", "总线", "地址", "内存映射", "外设寄存器",
             "NVIC", "时钟", "频率"]

    def setup(self):
        self.box((17, 11, 0.2), (0, 0, 0.1), theme.DIE)
        self.label("硅片（放大后）", (-7.2, 5.0, 0.3), 0.4, theme.TEXT_DIM,
                   align="left")
        self.blocks = {}
        self.positions = {}
        for key, name, color, x, y, _ in BLOCKS:
            node = self.root.attachNewNode(key)
            node.setPos(x, y, BLOCK_Z)
            self.box((2.5, 2.1, 0.5), (0, 0, 0), color, parent=node, pick=key)
            self.label(name, (0, 0, 1.2), 0.38, parent=node)
            self.blocks[key] = node
            self.positions[key] = (x, y)
            # 连到总线的支路
            edge = y - 1.05 if y > 0 else y + 1.05
            self.box((0.35, abs(edge - BUS_Y), 0.12), (x, (edge + BUS_Y) / 2, 0.26),
                     (0.85, 0.75, 0.45, 1))
        self.bus = self.box((15, 0.6, 0.15), (0, BUS_Y, 0.28), (0.9, 0.78, 0.4, 1))
        self.label("系统总线 Bus", (-7.4, BUS_Y + 0.65, 0.5), 0.36, theme.ACCENT,
                   align="left")

        # 芯片外面的一个 LED，接在 GPIO 上
        self.led = parts.LED(self.root, (-5.6, -6.2, 0), label="引脚上的 LED")
        self.wire([(-5.6, BOT_Y - 1.05, 0.3), (-5.6, -5.9, 0.3)], theme.COPPER, 4)

        self.selected = None
        self.hovered = None
        self.demo_i = None
        self.demo_wait = 0.0
        self.accept("space", self.start_demo)
        self.set_body(INTRO)

    # ---------- 悬停与点击 ----------
    def on_hover(self, tag):
        self.hovered = tag

    def on_pick(self, tag):
        for key, name, _, _, _, desc in BLOCKS:
            if key == tag:
                self.selected = key
                extra = ADDRESS.get(key, "")
                self.set_body(desc + ("\n\n" + extra if extra else "")
                              + "\n\n（点击其他模块继续探索，按空格看指令演示）")

    # ---------- 指令演示 ----------
    def bus_path(self, a, b):
        (xa, ya), (xb, yb) = self.positions[a], self.positions[b]
        z = 0.75
        return [(xa, ya, z), (xa, BUS_Y, z), (xb, BUS_Y, z), (xb, yb, z)]

    def start_demo(self):
        self.clear_movers()
        self.led.set_on(False)
        self.demo_i = -1
        self.next_demo()

    def next_demo(self):
        self.demo_i += 1
        if self.demo_i >= len(DEMO):
            self.demo_i = None
            self.set_body("演示结束！一条指令就是这样经过“取指 → 译码执行 → 访问"
                          "存储器/外设”完成的。\n\nMCU 每秒重复这个过程几千万次。\n\n"
                          "再按空格可以重看；点击模块查看介绍。")
            return
        src, dst, color, label, text = DEMO[self.demo_i]
        self.set_body("指令演示（%d/%d）\n\n%s" % (self.demo_i + 1, len(DEMO), text))
        self.selected = src
        if dst is None:
            self.demo_wait = 1.6
        else:
            self.movers.append(parts.Packet(
                self.root, self.bus_path(src, dst), color, speed=5.0,
                label=label, on_done=lambda d=dst: self.arrive(d)))

    def arrive(self, dst):
        self.selected = dst
        if dst == "gpio":
            self.led.set_on(True)
        self.demo_wait = 1.2

    def update(self, dt):
        for key, node in self.blocks.items():
            lift = 0.5 if key in (self.hovered, self.selected) else 0.0
            z = node.getZ() + (BLOCK_Z + lift - node.getZ()) * min(1, dt * 8)
            node.setZ(z)
            if key == self.selected:
                k = 1.0 + 0.4 * parts.pulse(self.time, 6)
                node.setColorScale(k, k, k, 1)
            else:
                node.clearColorScale()
        if self.demo_i is not None and self.demo_wait > 0:
            self.demo_wait -= dt
            if self.demo_wait <= 0:
                self.next_demo()
