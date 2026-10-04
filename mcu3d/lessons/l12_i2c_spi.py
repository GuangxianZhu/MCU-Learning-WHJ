"""第 12 课：I2C 与 SPI——一条总线挂多个设备。"""

from .. import parts, theme
from ..ui import set_text
from .base import Lesson

M_X = -7.5            # 主机 MCU 的位置
BUS_X0, BUS_X1 = -5.6, 8.5
Z = 0.25              # 导线高度
TRAIN_Z = 0.55        # 比特方块高度
BIT_T = 0.32          # 每个比特的时间（演示）

# ---------------- I2C ----------------
SDA_Y, SCL_Y = 1.0, 0.0
I2C_DEV_Y = -3.2
I2C_DEVICES = [
    # (按键, 名称, 地址, 读/写, 数据, 数据说明, x)
    ("1", "温度传感器", 0x48, "R", 0x19, "温度 25℃", -1.5),
    ("2", "OLED 屏幕", 0x3C, "W", 0xAF, "命令：打开显示", 2.5),
    ("3", "EEPROM 存储", 0x50, "W", 0x42, "存入字母 'B'", 6.5),
]
I2C_FRAME = ["起始", "地址(7位)", "读/写", "应答", "数据(8位)", "应答", "停止"]

I2C_INTRO = (
    "I2C 只用两根线：SDA（数据）和 SCL（时钟），却能挂上很多设备。"
    "每个设备都有一个 7 位“地址”，就像门牌号。\n\n"
    "通信过程：\n"
    "① 起始：主机在 SCL 为高时把 SDA 拉低\n"
    "② 主机喊门牌号：发出 7 位地址 + 1 位读/写\n"
    "③ 所有设备都听到了，只有地址对上的那个回一个“应答”ACK（把 SDA 拉低）\n"
    "④ 传数据：写就是主机发给设备，读就是设备发给主机，每个字节后都有应答\n"
    "⑤ 停止：SCL 为高时 SDA 拉高\n\n"
    "SCL 由主机控制，每一拍传一位，所以 I2C 是“同步”通信（UART 没有时钟线，是“异步”）。"
    "两根线上都接了上拉电阻，平时是高电平。")

# ---------------- SPI ----------------
SCK_Y, MOSI_Y, MISO_Y, CS1_Y, CS2_Y = 1.8, 1.0, 0.2, -0.6, -1.4
SPI_DEV_Y = -3.6
SPI_DEVICES = [
    # (按键, 名称, 片选线 y, 发送, 收到, 说明, x)
    ("1", "LCD 屏幕", CS1_Y, 0xA5, 0x00, "屏幕只收数据，回来的是 0", 2.5),
    ("2", "Flash 芯片", CS2_Y, 0x9F, 0xEF,
     "主机发 0x9F“读ID”，Flash 同时回 0xEF（厂商编号）", 6.5),
]

SPI_INTRO = (
    "SPI 用 4 根线：\n"
    "· SCK：时钟，由主机发出\n"
    "· MOSI：主机发 → 设备收（Master Out Slave In）\n"
    "· MISO：设备发 → 主机收（Master In Slave Out）\n"
    "· CS：片选，每个设备单独一根，拉低表示“我在跟你说话”\n\n"
    "SPI 不用地址：要和哪个设备说话，就把它的 CS 拉低。"
    "发送和接收在两根线上同时进行（全双工），所以速度很快，"
    "常用于屏幕、Flash 存储芯片、SD 卡。\n\n"
    "I2C 与 SPI 对比：\n"
    "I2C：2 根线，靠地址选设备，较慢（100k~400k 位/秒）\n"
    "SPI：3 根线 + 每个设备 1 根 CS，靠片选，很快（几~几十 M 位/秒）")


def bits8(value):
    """高位在前的 8 个比特（I2C、SPI 都是高位先发）。"""
    return [value >> (7 - i) & 1 for i in range(8)]


class I2CSPILesson(Lesson):
    title = "I2C 与 SPI"
    summary = "两根线挂一串设备 / 四根线高速传输"
    hints = ("M 切换 I2C / SPI\n"
             "I2C：1 读温度传感器  2 写屏幕  3 写 EEPROM  4 喊一个不存在的地址\n"
             "SPI：1 和屏幕通信  2 读 Flash 的 ID")
    camera = (33, 0, -45, (0.8, -0.3, 0.5))
    location = ["i2c", "bus", "pins"]
    location_text = (
        "主机 MCU 里的 I2C / SPI 外设（芯片下排青绿色那块）。和上一课的 UART 一样，"
        "它们内部也有数据寄存器、移位寄存器和状态寄存器：CPU 把字节写进数据寄存器，"
        "外设按时序把它变成引脚上的高低电平。I2C 的 SDA/SCL、SPI 的 SCK/MOSI/MISO/CS "
        "都是借给这些外设使用的 GPIO 引脚。")
    link_text = (
        "和上一课的 UART 对比：多了一根时钟线（同步），一条总线能挂多个设备；外设内部同样是“数据寄存器 + 移位寄存器”。")
    apply_text = (
        "连接温湿度传感器、OLED 屏幕、EEPROM 存储芯片、SD 卡。温度报警器可以加一块 OLED 屏显示温度（可选）。")
    sim_program = "inc"
    terms = ["I2C", "SDA", "SCL", "主机", "从机", "设备地址", "ACK", "NACK", "上拉电阻",
             "同步", "SPI", "SCK", "MOSI", "MISO", "CS", "全双工"]

    def setup(self):
        self.mode = "i2c"
        self.busy = False
        self.wait_t = 0.0
        self.wait_next = None
        self.status = "按数字键开始一次通信。"
        self.clock_lines = []

        self.box((19, 9.5, 0.2), (0.6, -1.0, -0.1), theme.PCB)
        self.master = parts.Chip(self.root, size=3, pos=(M_X, 0, 0), label="主机")
        self.label("主机 MCU", (M_X, 2.4, 0.4), 0.4)

        self.i2c_root = self.root.attachNewNode("i2c")
        self.spi_root = self.root.attachNewNode("spi")
        self._build_i2c()
        self._build_spi()

        for k in "1234":
            self.accept(k, self.start, [int(k)])
        self.accept("m", self.toggle_mode)
        self.show_mode()

    # ------------------------------------------------------------ 场景
    def _bus_line(self, y, color, parent, x1=BUS_X1):
        return self.wire([(BUS_X0, y, Z), (x1, y, Z)], color, 4, parent=parent)

    def _device(self, parent, x, y, name, sub):
        node = parent.attachNewNode(name)
        node.setPos(x, y, 0)
        body = self.box((2.8, 1.6, 0.6), (0, 0, 0.3), (0.2, 0.22, 0.3, 1), parent=node)
        self.label(name, (0, 0, 1.4), 0.34, parent=node)
        self.label(sub, (0, -1.2, 0.3), 0.28, theme.TEXT_DIM, parent=node)
        return node, body

    def _build_i2c(self):
        r = self.i2c_root
        self.sda = self._bus_line(SDA_Y, theme.HIGH, r)
        self.scl = self._bus_line(SCL_Y, theme.HIGH, r)
        self.label("SDA 数据", (BUS_X1 + 0.3, SDA_Y, Z), 0.3, theme.TEXT_DIM,
                   align="left", parent=r)
        self.label("SCL 时钟", (BUS_X1 + 0.3, SCL_Y, Z), 0.3, theme.TEXT_DIM,
                   align="left", parent=r)
        self.box((0.3, 0.7, 0.3), (-4.6, 2.0, 0.15), (0.9, 0.8, 0.6, 1), parent=r)
        self.wire([(-4.6, 1.65, Z), (-4.6, SDA_Y, Z)], parent=r)
        self.label("上拉电阻 → 3.3V", (-4.6, 2.9, 0.3), 0.26, theme.TEXT_DIM, parent=r)
        self.i2c_devs = []
        for key, name, addr, rw, data, desc, x in I2C_DEVICES:
            node, body = self._device(r, x, I2C_DEV_Y, name, "地址 0x%02X" % addr)
            top = I2C_DEV_Y + 0.8
            self.wire([(x - 0.4, SDA_Y, Z), (x - 0.4, top, Z)], theme.WIRE_IDLE, 3, r)
            self.wire([(x + 0.4, SCL_Y, Z), (x + 0.4, top, Z)], theme.WIRE_IDLE, 3, r)
            reply = self.label("", (0, 0, 2.0), 0.32, theme.ACCENT, parent=node)
            self.i2c_devs.append((body, reply))
        # 帧格式条
        self.frame_labels = []
        for i, name in enumerate(I2C_FRAME):
            x = -4.5 + i * 2.0
            self.frame_labels.append(self.label(name, (x, 3.2, 1.5), 0.3,
                                                theme.TEXT_DIM, parent=r))
        self.label("一帧的顺序：", (-5.8, 3.2, 1.5), 0.3, theme.TEXT_DIM,
                   align="right", parent=r)

    def _build_spi(self):
        r = self.spi_root
        self.sck = self._bus_line(SCK_Y, theme.HIGH, r)
        self.mosi = self._bus_line(MOSI_Y, theme.WIRE_IDLE, r)
        self.miso = self._bus_line(MISO_Y, theme.WIRE_IDLE, r)
        for y, name in ((SCK_Y, "SCK 时钟"), (MOSI_Y, "MOSI 主→从"),
                        (MISO_Y, "MISO 从→主")):
            self.label(name, (BUS_X1 + 0.3, y, Z), 0.3, theme.TEXT_DIM,
                       align="left", parent=r)
        self.cs_lines = []
        self.spi_devs = []
        for key, name, cs_y, tx, rx, desc, x in SPI_DEVICES:
            node, body = self._device(r, x, SPI_DEV_Y, name, "")
            top = SPI_DEV_Y + 0.8
            for dx, y in ((-0.6, SCK_Y), (-0.2, MOSI_Y), (0.2, MISO_Y)):
                self.wire([(x + dx, y, Z), (x + dx, top, Z)], theme.WIRE_IDLE, 2, r)
            cs = self.wire([(BUS_X0, cs_y, Z), (x + 0.6, cs_y, Z), (x + 0.6, top, Z)],
                           theme.HIGH, 4, r)
            self.label("CS%s" % key, (BUS_X0 + 0.3, cs_y + 0.3, Z), 0.26,
                       theme.TEXT_DIM, align="left", parent=r)
            reply = self.label("", (0, 0, 2.0), 0.32, theme.ACCENT, parent=node)
            self.cs_lines.append(cs)
            self.spi_devs.append((body, reply))

    # ------------------------------------------------------------ 控制
    def toggle_mode(self):
        if self.busy:
            return
        self.mode = "spi" if self.mode == "i2c" else "i2c"
        self.status = "按数字键开始一次通信。"
        self.show_mode()

    def show_mode(self):
        if self.mode == "i2c":
            self.i2c_root.show()
            self.spi_root.hide()
        else:
            self.i2c_root.hide()
            self.spi_root.show()
        self.reset_visuals()
        self.refresh()

    def reset_visuals(self):
        for body, reply in self.i2c_devs + self.spi_devs:
            body.clearColorScale()
            set_text(reply, "")
        for lbl in self.frame_labels:
            lbl.node().setTextColor(*theme.TEXT_DIM)
        for line in (self.sda, self.scl, self.sck):
            line.setColor(*theme.HIGH[:3], 1, 1)
        for cs in self.cs_lines:
            cs.setColor(*theme.HIGH[:3], 1, 1)
        self.stop_clock()

    def stop_clock(self):
        for line in self.clock_lines:
            line.setColor(*theme.HIGH[:3], 1, 1)
        self.clock_lines = []

    def refresh(self):
        intro = I2C_INTRO if self.mode == "i2c" else SPI_INTRO
        name = "【I2C 模式】" if self.mode == "i2c" else "【SPI 模式】"
        self.set_body(name + "（按 M 切换）\n\n" + intro + "\n\n当前：" + self.status)

    def say(self, text):
        self.status = text
        self.refresh()

    def wait(self, seconds, then):
        self.wait_t = seconds
        self.wait_next = then

    def start(self, n):
        if self.busy:
            return
        if self.mode == "i2c" and 1 <= n <= 4:
            self.busy = True
            self.reset_visuals()
            self.i2c_start(n - 1)
        elif self.mode == "spi" and 1 <= n <= 2:
            self.busy = True
            self.reset_visuals()
            self.spi_start(n - 1)

    def finish(self, text):
        self.busy = False
        self.stop_clock()
        self.say(text + "\n\n（再按数字键试试别的设备）")

    def highlight_frame(self, i):
        for k, lbl in enumerate(self.frame_labels):
            lbl.node().setTextColor(*(theme.ACCENT if k == i else theme.TEXT_DIM))

    # ------------------------------------------------------------ I2C 流程
    def i2c_start(self, idx):
        if idx < len(I2C_DEVICES):
            _, name, addr, rw, data, desc, x = I2C_DEVICES[idx]
        else:
            name, addr, rw, data, desc, x = None, 0x77, "W", 0, "", None
        self.cur = (idx, name, addr, rw, data, desc, x)
        self.highlight_frame(0)
        self.sda.setColor(*theme.LOW[:3], 1, 1)
        self.say("① 起始信号：SCL 保持高电平时，主机把 SDA 拉低，"
                 "所有设备都开始注意听。")
        self.wait(1.4, self.i2c_address)

    def i2c_address(self):
        idx, name, addr, rw, data, desc, x = self.cur
        self.highlight_frame(1)
        self.clock_lines = [self.scl]
        bits = [addr >> (6 - i) & 1 for i in range(7)] + [1 if rw == "R" else 0]
        labels = [str(b) for b in bits[:7]] + [rw]
        rw_text = "读（1）" if rw == "R" else "写（0）"
        self.say("② 主机发出地址 0x%02X = %s，再加 1 位 %s。"
                 "地址是高位先发。总线上的每个设备都会收到。"
                 % (addr, format(addr, "07b"), rw_text))
        self.movers.append(parts.BitTrain(
            self.i2c_root, bits, (BUS_X0, SDA_Y, TRAIN_Z), (BUS_X1, SDA_Y, TRAIN_Z),
            BIT_T, 0.8, labels, on_bit=self._addr_bit, on_done=self.i2c_compare))

    def _addr_bit(self, i):
        self.highlight_frame(2 if i == 7 else 1)

    def i2c_compare(self):
        idx = self.cur[0]
        for k, (body, reply) in enumerate(self.i2c_devs):
            if k == idx:
                body.setColorScale(0.6, 1.8, 0.6, 1)
                set_text(reply, "是我！")
            else:
                body.setColorScale(0.5, 0.5, 0.5, 1)
                set_text(reply, "不是我")
        self.stop_clock()
        self.wait(1.0, self.i2c_ack)

    def i2c_ack(self):
        idx, name, addr, rw, data, desc, x = self.cur
        self.highlight_frame(3)
        if name is None:
            self.say("③ 没有任何设备的地址是 0x%02X，没人把 SDA 拉低，"
                     "主机读到的是高电平 = NACK（没有应答）。"
                     "程序就知道：这个设备不存在或者没接好。" % addr)
            self.wait(2.2, lambda: self.i2c_stop("通信失败：地址 0x%02X 无应答。"
                                                 "实际开发中这是最常见的排错线索！" % addr))
            return
        self.say("③ %s 发现地址是自己的，回一个应答 ACK：把 SDA 拉低（0）。" % name)
        self.clock_lines = [self.scl]
        self.movers.append(parts.BitTrain(
            self.i2c_root, [0], (x - 0.4, SDA_Y, TRAIN_Z), (BUS_X0, SDA_Y, TRAIN_Z),
            BIT_T, 0.8, ["ACK"], on_done=self.i2c_data))

    def i2c_data(self):
        idx, name, addr, rw, data, desc, x = self.cur
        self.highlight_frame(4)
        bits = bits8(data)
        if rw == "R":
            self.say("④ 读数据：%s 把 0x%02X（%s）一位一位发给主机。" % (name, data, desc))
            start, end = (x - 0.4, SDA_Y, TRAIN_Z), (BUS_X0, SDA_Y, TRAIN_Z)
        else:
            self.say("④ 写数据：主机把 0x%02X（%s）发给 %s。" % (data, desc, name))
            start, end = (BUS_X0, SDA_Y, TRAIN_Z), (x - 0.4, SDA_Y, TRAIN_Z)
        self.movers.append(parts.BitTrain(
            self.i2c_root, bits, start, end, BIT_T, 0.8, on_done=self.i2c_ack2))

    def i2c_ack2(self):
        idx, name, addr, rw, data, desc, x = self.cur
        self.highlight_frame(5)
        body, reply = self.i2c_devs[idx]
        if rw == "R":
            self.say("⑤ 主机收到了，回一个 NACK（不拉低）表示“够了，不用再发”。")
            bits, labels = [1], ["NACK"]
            start, end = (BUS_X0, SDA_Y, TRAIN_Z), (x - 0.4, SDA_Y, TRAIN_Z)
        else:
            set_text(reply, "收到 0x%02X" % data)
            self.say("⑤ %s 收到数据，回应答 ACK。" % name)
            bits, labels = [0], ["ACK"]
            start, end = (x - 0.4, SDA_Y, TRAIN_Z), (BUS_X0, SDA_Y, TRAIN_Z)
        self.movers.append(parts.BitTrain(
            self.i2c_root, bits, start, end, BIT_T, 0.8, labels,
            on_done=lambda: self.i2c_stop(
                "完成：主机读到 0x%02X = %s。" % (data, desc) if rw == "R"
                else "完成：%s 已收到“%s”。" % (name, desc))))

    def i2c_stop(self, result):
        self.highlight_frame(6)
        self.stop_clock()
        self.sda.setColor(*theme.HIGH[:3], 1, 1)
        self.scl.setColor(*theme.HIGH[:3], 1, 1)
        self.say("⑥ 停止信号：SCL 为高时 SDA 拉高，总线恢复空闲。")
        self.wait(1.2, lambda: self.finish(result))

    # ------------------------------------------------------------ SPI 流程
    def spi_start(self, idx):
        key, name, cs_y, tx, rx, desc, x = SPI_DEVICES[idx]
        self.cur = (idx, name, cs_y, tx, rx, desc, x)
        self.cs_lines[idx].setColor(*theme.LOW[:3], 1, 1)
        self.spi_devs[idx][0].setColorScale(0.6, 1.8, 0.6, 1)
        for k, (body, reply) in enumerate(self.spi_devs):
            if k != idx:
                body.setColorScale(0.5, 0.5, 0.5, 1)
        self.say("① 主机把 CS%s 拉低：选中 %s。另一个设备的 CS 还是高电平，"
                 "它会忽略总线上的一切。" % (key, name))
        self.wait(1.4, self.spi_transfer)

    def spi_transfer(self):
        idx, name, cs_y, tx, rx, desc, x = self.cur
        self.clock_lines = [self.sck]
        self.say("② SCK 每跳一下，MOSI 和 MISO 上各传一位：主机发 0x%02X 的同时，"
                 "%s 也在回 0x%02X。这就是“全双工”。" % (tx, name, rx))
        self.pending = 2
        self.movers.append(parts.BitTrain(
            self.spi_root, bits8(tx), (BUS_X0, MOSI_Y, TRAIN_Z),
            (x - 0.2, MOSI_Y, TRAIN_Z), BIT_T, 0.8, on_done=self._spi_part_done))
        self.movers.append(parts.BitTrain(
            self.spi_root, bits8(rx), (x + 0.2, MISO_Y, TRAIN_Z),
            (BUS_X0, MISO_Y, TRAIN_Z), BIT_T, 0.8, on_done=self._spi_part_done))

    def _spi_part_done(self):
        self.pending -= 1
        if self.pending:
            return
        idx, name, cs_y, tx, rx, desc, x = self.cur
        self.stop_clock()
        set_text(self.spi_devs[idx][1], "收到 0x%02X" % tx)
        self.cs_lines[idx].setColor(*theme.HIGH[:3], 1, 1)
        self.say("③ 8 位传完，主机把 CS%d 拉高，结束这次通信。" % (idx + 1))
        self.wait(1.2, lambda: self.finish(
            "完成：%s 收到 0x%02X，主机收到 0x%02X。%s" % (name, tx, rx, desc)))

    # ------------------------------------------------------------ 每帧
    def update(self, dt):
        if self.wait_next and self.wait_t > 0:
            self.wait_t -= dt
            if self.wait_t <= 0:
                nxt, self.wait_next = self.wait_next, None
                nxt()
        # 时钟线：传输时高低交替闪动
        high = int(self.time / (BIT_T / 2)) % 2 == 0
        c = theme.HIGH if high else theme.LOW
        for line in self.clock_lines:
            line.setColor(c[0], c[1], c[2], 1, 1)
