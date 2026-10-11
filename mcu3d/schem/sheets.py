"""芯片的各层电路图，像 Logisim 的“子电路”一样可以一层层双击进去：

    整颗芯片 ─ CPU 内核 ─┬─ 寄存器组 ─ 某个寄存器（32 个 D 触发器）─ 一个 D 触发器（与非门）
                          ├─ PC（也是一个寄存器）
                          └─ ALU（一排全加器）─ 一位全加器（与门、或门、异或门）

每张图有 build()（画出来）和 apply(state)（按当前状态给导线上色、改数值）。
只有 ALU 和寄存器画到了门电路这一层，其余部分停在方块这一层：
一整颗 CPU 画成门电路有几万个门，一屏看不下。
"""

from ..sim.asm import REG_NAMES
from ..sim.machine import add_with_carry
from . import logic
from .draw import INK, INK_DIM

MASK = 0xFFFFFFFF


def _b(v):
    return "x" if v is None else str(v)


def _short(v):
    """多位引脚框里只放得下两位十六进制，大的数看旁边导线上写的值。"""
    if v is None:
        return "x"
    return "%X" % v if v <= 0xFF else "…"


class Sheet:
    key = ""
    bounds = (0, 0, 10, 10)

    def __init__(self, canvas, param=None):
        self.c = canvas
        self.param = param
        # 标签 -> (名称, 介绍, 双击进入的下一层 (key, param) 或 None)
        self.picks = {}
        self.build()

    def title(self):
        return ""

    def build(self):
        pass

    def apply(self, st):
        pass

    def net(self, wires, value, active=False):
        for w in wires:
            w.set(value, active)


# =====================================================================
# 第 1 层：整颗芯片
# =====================================================================
class ChipSheet(Sheet):
    key = "chip"
    bounds = (-11, -0.5, 47, 30.5)

    def title(self):
        return "整颗芯片"

    def build(self):
        c = self.c
        c.text("芯片内部：CPU 通过系统总线访问 Flash、SRAM 和外设", -10, 29.4, 0.75, INK)
        self.clk_pin, self.clk_val = c.pin_in(-2, 24, "时钟 CLK", tag="clk")
        self.rst_pin, self.rst_val = c.pin_in(-2, 20, "复位 RESET", tag="reset")
        self.clk = c.wire([(-1.7, 24), (2, 24)])
        self.rst = c.wire([(-1.7, 20), (2, 20)])
        self.cpu = c.box(2, 2, 12, 28, "CPU 内核", tag="cpu", title_size=1.0,
                         sub="双击进入看里面")
        c.text("Cortex-M3（简化）", 7, 25.0, 0.55, INK_DIM, "center")
        for name, z in (("A 地址", 16), ("D 数据", 14), ("RD 读", 12), ("WR 写", 10)):
            c.text(name, 11.7, z - 0.22, 0.56, INK, "right")
        c.text("CLK", 2.3, 23.78, 0.56, INK)
        c.text("RESET", 2.3, 19.78, 0.56, INK)

        rails = {"a": (16, 32, "地址线 A", "bus_addr"), "d": (14, 32, "数据线 D", "bus_data"),
                 "rd": (12, 1, "读 RD", "bus_rd"), "wr": (10, 1, "写 WR", "bus_wr")}
        self.nets = {}
        for key, (z, bits, name, tag) in rails.items():
            w = c.wire([(12, z), (38, z)], bits, probe=(38.4, z - 0.25), prefix="", tag=tag)
            c.text(name, 37.8, z + 0.25, 0.50, INK_DIM, "right")
            self.nets[key] = [w]
        c.text("系统总线", 37.8, 17.3, 0.55, INK, "right")

        # Flash / SRAM 在总线上方，从下边伸出引脚接到总线
        self.blocks = {}
        specs = [("flash", 15, 20, "Flash", "0x0800 0000 起 · 放程序", ("a", "d", "rd")),
                 ("sram", 27, 20, "SRAM", "0x2000 0000 起 · 放变量和栈", ("a", "d", "rd", "wr"))]
        for key, x0, z0, name, sub, pins in specs:
            self.blocks[key] = c.box(x0, z0, x0 + 8, z0 + 8, name, tag=key, sub=sub)
            for k, p in enumerate(pins):
                x = x0 + 1 + 1.5 * k
                zr = rails[p][0]
                self.nets[p].append(c.wire([(x, z0), (x, zr)], rails[p][1]))
                c.dot(x, zr)
                c.text(p.upper(), x, z0 + 1.6, 0.48, INK_DIM, "center")
            c.text("CS", x0 + 0.3, z0 + 5.78, 0.50, INK_DIM)
        # 外设区在总线下方
        self.blocks["periph"] = c.box(27, 1, 35, 7, "外设区", tag="periph",
                                      sub="0x4000 0000 起 · 第 8 课起接入")
        for k, p in enumerate(("a", "d", "rd", "wr")):
            x = 28 + 1.5 * k
            zr = rails[p][0]
            self.nets[p].append(c.wire([(x, 7), (x, zr)], rails[p][1]))
            c.dot(x, zr)
        c.text("CS", 27.3, 2.78, 0.50, INK_DIM)
        # 地址译码器：看地址，决定选中哪一块
        self.blocks["decoder"] = c.box(15, 1, 23, 7, "地址译码器", tag="decoder",
                                       title_size=0.6, sub="看地址的最高几位")
        self.nets["a"].append(c.wire([(21, 16), (21, 7)], 32))
        c.dot(21, 16)
        self.cs = {
            "flash": c.wire([(15, 5.0), (13.5, 5.0), (13.5, 26), (15, 26)], tag="cs"),
            "sram": c.wire([(23, 5.0), (25, 5.0), (25, 26), (27, 26)], tag="cs"),
            "periph": c.wire([(23, 3), (27, 3)], tag="cs"),
        }
        c.text("选中 Flash", 15.3, 4.75, 0.46, INK_DIM)
        c.text("选中 SRAM", 22.7, 5.25, 0.46, INK_DIM, "right")
        c.text("选中外设", 22.7, 2.4, 0.46, INK_DIM, "right")

        self.picks = {
            "cpu": ("CPU 内核",
                    "CPU 是芯片的“大脑”：从 Flash 取出机器码，看懂它，再去计算或读写存储器。\n\n"
                    "它对外只有几组线：地址线 A、数据线 D、读线 RD、写线 WR，再加上时钟和复位。"
                    "芯片里其他所有部分，都是通过这几组线和 CPU 打交道的。\n\n"
                    "双击它，看 CPU 里面有什么。", ("cpu", None)),
            "flash": ("Flash 程序存储器（0x0800 0000 起）",
                      "存放程序的地方，断电不丢。最前面是向量表（第 0 个字是栈顶地址，第 1 个字是复位后"
                      "第一条指令的地址），后面是一条条机器码，再后面是“文字池”（程序要用的常数）。\n\n"
                      "它只接了 A、D、RD：运行时只能读，不能写。\n"
                      "只有地址译码器把它的 CS（片选）线拉到 1 时，它才会把数据放到数据线上。", None),
            "sram": ("SRAM 数据存储器（0x2000 0000 起，20KB）",
                     "存放运行时数据，读写都快，断电就丢。低地址放全局变量，高地址（0x2000 5000 往下）是栈。\n\n"
                     "它接了 A、D、RD、WR 四组线：RD=1 时把数据放上数据线，WR=1 时把数据线上的数存下来。\n"
                     "CPU 不能直接在这里做计算，要先读进寄存器，算完再写回来。", None),
            "periph": ("外设区（0x4000 0000 起）",
                       "GPIO、定时器、UART、ADC 等外设的寄存器都在这段地址里。CPU 读写它们和读写 SRAM 一模一样，"
                       "只是写进去的数会变成引脚电平、定时时间、串口数据……第 8 课起会把它们接进来。", None),
            "decoder": ("地址译码器",
                        "一块组合逻辑电路：看地址线的最高几位，决定这次访问的是谁。\n\n"
                        "· 0x08… → 把“选中 Flash”拉到 1\n· 0x20… → 把“选中 SRAM”拉到 1\n"
                        "· 0x40… → 把“选中外设”拉到 1\n\n"
                        "每块存储器只有自己的 CS（Chip Select，片选）线是 1 时才响应，"
                        "所以几块存储器可以共用同一组地址线和数据线而不打架。", None),
            "cs": ("片选线 CS",
                   "Chip Select。地址译码器给每一块存储器或外设单独拉一根线，是 1 就表示“这次找的是你”。"
                   "一次总线访问中最多只有一根是 1。", None),
            "clk": ("时钟 CLK",
                    "一根不停在 0 和 1 之间来回跳的线。CPU 和寄存器都跟着它的节拍走：每次从 0 跳到 1"
                    "（上升沿），寄存器就把输入端的值存进去。\n\n"
                    "按 T 走一拍，就能看到这根线先是 0、再变成 1。真实芯片里它每秒跳几千万次。", None),
            "reset": ("复位 RESET",
                      "按下复位后，CPU 一切从头开始：先从 Flash 的向量表读出栈顶地址放进 SP，"
                      "再读出第一条指令的地址放进 PC。按 Z 复位后，这根线是 1，执行第一步时它回到 0。", None),
            "bus_addr": ("地址线 A[31:0]",
                         "32 根线并排，画成一根粗黑线（Logisim 里叫“总线”），旁边写着它现在的值。"
                         "CPU 在上面放出要访问的地址；没有访问时没人驱动它，就是蓝色（悬空）。", None),
            "bus_data": ("数据线 D[31:0]",
                         "32 根线，传送真正的数据。读的时候由被选中的存储器放数据，写的时候由 CPU 放数据。"
                         "数据线是双向的。", None),
            "bus_rd": ("读线 RD", "1 根线。CPU 要读的时候把它拉到 1（亮绿），被选中的存储器就把数据放上数据线。", None),
            "bus_wr": ("写线 WR", "1 根线。CPU 要写的时候把它拉到 1（亮绿），被选中的存储器就把数据线上的数存下来。", None),
        }

    def apply(self, st):
        addr, data, rd, wr = st.bus()
        busy = st.now("fetch", "mem_read", "mem_write")
        self.net(self.nets["a"], addr, busy)
        self.net(self.nets["d"], data, busy)
        self.net(self.nets["rd"], rd, busy and rd)
        self.net(self.nets["wr"], wr, busy and wr)
        region = st.region()
        for key, w in self.cs.items():
            w.set(None if addr is None else int(region == key))
        self.clk.set(st.clk)
        self.clk_val.node().setText(str(st.clk))
        rst = int(st.need_reset)
        self.rst.set(rst)
        self.rst_val.node().setText(str(rst))
        self.cpu.set_active(st.active)
        for key, blk in self.blocks.items():
            on = busy and (region == key or key == "decoder")
            blk.set_active(on)


# =====================================================================
# 第 2 层：CPU 内核
# =====================================================================
class CPUSheet(Sheet):
    key = "cpu"
    bounds = (-4, -1.5, 50, 35.5)

    def title(self):
        return "CPU 内核"

    def build(self):
        c = self.c
        c.text("CPU 内部的数据通路（右边几个引脚就是上一层的 A、D、RD、WR）", -3.5, 34.9, 0.7)
        w = {}
        # ---- PC 和它的“下一条地址” ----
        self.pcmux, ins, out, sel = c.mux(0, 28, 2, tag="pcmux")
        self.pc = c.box(3, 26, 9, 30, "PC 程序计数器", tag="pc", title_size=0.55)
        self.pc_text = c.text("", 6, 26.5, 0.6, INK, "center")
        w["pcin"] = [c.wire([out, (3, 28)], 32)]
        w["pc"] = [c.wire([(9, 28), (11, 28)], 32), c.wire([(11, 28), (11, 32), (12, 32)], 32),
                   c.wire([(11, 28), (11, 24.8), (38, 24.8)], 32, probe=(26, 25.1), prefix="PC → ")]
        c.dot(11, 28)
        self.plus2 = c.box(12, 31, 16, 33, "+2", tag="plus2", title_size=0.7)
        w["pc2"] = [c.wire([(16, 32), (17, 32), (17, 34.3), (-2, 34.3), (-2, ins[0][1]),
                            ins[0]], 32, probe=(17.4, 33.4), prefix="PC+2 = ")]
        c.text("下一条", -0.2, ins[0][1] + 0.2, 0.44, INK_DIM, "right")
        c.text("跳转目标", -1.2, ins[1][1] - 0.6, 0.44, INK_DIM, "right")
        # ---- 地址选择器：取指时送 PC，读写数据时送算出来的地址 ----
        self.amux, a_ins, a_out, a_sel = c.mux(38, 24, 2, tag="amux")
        w["aout"] = [c.wire([a_out, (43.7, 24)], 32, probe=(39.9, 24.35))]
        _, self.a_val = c.pin_out(44, 24, "A 地址")
        # ---- 指令寄存器、控制单元 ----
        self.ir = c.box(26, 26, 32, 30, "IR 指令寄存器", tag="ir", title_size=0.55)
        self.ir_text = c.text("", 29, 26.6, 0.6, INK, "center")
        w["ir"] = [c.wire([(29, 26), (29, 22)], 16)]
        self.ctrl = c.box(26, 15, 34, 22, "控制单元（译码器）", tag="control", title_size=0.55)
        self.ctrl_text = c.text("", 30, 17.8, 0.55, INK, "center")
        w["fetch"] = [c.wire([(34, 21), (a_sel[0], 21), a_sel])]
        c.text("取指", 34.3, 21.2, 0.46, INK_DIM)
        w["rd"] = [c.wire([(34, 19), (43.7, 19)])]
        _, self.rd_val = c.pin_out(44, 19, "RD 读")
        w["wr"] = [c.wire([(34, 17.5), (43.7, 17.5)])]
        _, self.wr_val = c.pin_out(44, 17.5, "WR 写")
        w["br"] = [c.wire([(26, 20.5), (sel[0], 20.5), sel])]
        c.text("跳转", 25.7, 20.7, 0.46, INK_DIM, "right")
        w["we"] = [c.wire([(28, 15), (28, 1.5), (3, 1.5), (3, 6), (4, 6)])]
        c.text("写寄存器", 28.3, 14.3, 0.46, INK_DIM)
        # ---- 数据线 D：取指进 IR、读数据进写回选择器、写数据从寄存器组出来 ----
        _, self.d_val = c.pin_out(44, 12, "D 数据")
        w["d"] = [c.wire([(43.7, 12), (36, 12)], 32, probe=(37.3, 12.35))]
        w["d_ir"] = [c.wire([(36, 12), (36, 28), (32, 28)], 32)]
        w["d_load"] = [c.wire([(36, 12), (36, -0.5), (-2.5, -0.5), (-2.5, 8.2), (0.5, 8.2)], 32)]
        w["d_store"] = [c.wire([(13, 5.5), (13, 0.5), (37, 0.5), (37, 12)], 32)]
        c.dot(36, 12)
        c.dot(37, 12)
        c.dot(13, 5.5)
        # ---- 寄存器组、写回选择器 ----
        self.rf = c.box(4, 3, 11, 13, "寄存器组", tag="regfile", title_size=0.7,
                        sub="双击进入")
        self.rf_text = c.text("", 7.5, 8.2, 0.5, INK, "center")
        for name, x, z, al in (("WD", 4.2, 9, "left"), ("WE", 4.2, 6, "left"),
                               ("A", 10.8, 10.5, "right"), ("B", 10.8, 5.5, "right")):
            c.text(name, x, z - 0.2, 0.50, INK_DIM, al)
        self.wbmux, wb_ins, wb_out, _ = c.mux(0.5, 9, 2, tag="wbmux")
        w["wd"] = [c.wire([wb_out, (4, 9)], 32)]
        # ---- ALU 和标志位 ----
        from .draw import Shape
        self.alu = Shape(c, [(15, 4), (21, 6), (21, 10), (15, 12), (15, 9), (16, 8), (15, 7)],
                         tag="alu")
        c.text("ALU", 18.2, 7.7, 0.9, INK, "center")
        c.text("双击进入", 18.2, 6.6, 0.50, INK_DIM, "center")
        w["rfa"] = [c.wire([(11, 10.5), (15, 10.5)], 32, probe=(11.3, 10.85), prefix="A=")]
        w["rfb"] = [c.wire([(11, 5.5), (15, 5.5)], 32, probe=(13.3, 5.85), prefix="B=")]
        w["y"] = [c.wire([(21, 7), (24, 7)], 32),
                  c.wire([(24, 7), (24, 23.2), a_ins[1]], 32),
                  c.wire([(24, 22.5), (-1, 22.5), (-1, ins[1][1]), ins[1]], 32,
                         probe=(9.5, 22.8), prefix="ALU 结果 → "),
                  c.wire([(24, 7), (24, 2.5), (-1, 2.5), (-1, wb_ins[0][1]), wb_ins[0]], 32)]
        c.dot(24, 7)
        c.dot(24, 22.5)
        c.text("算出的地址", 37.7, 23.45, 0.44, INK_DIM, "right")
        self.flags_box = c.box(18, 15, 23, 18, "", tag="flags")
        c.text("标志位", 20.5, 18.3, 0.5, INK, "center")
        self.flag_text = [c.text("", 18.65 + 1.25 * k, 16.0, 0.56, INK, "center")
                          for k in range(4)]
        w["nzcv"] = [c.wire([(21, 9), (22, 9), (22, 15)], 4)]
        self.flag_lines = [c.wire([(23, 15.6 + 0.6 * k), (26, 15.6 + 0.6 * k)]) for k in range(4)]
        self.w = w

        self.picks = {
            "pc": ("PC 程序计数器（R15）",
                   "存着“下一条指令在 Flash 的哪个地址”。它本身就是一个 32 位寄存器。\n\n"
                   "每次取指后，左边的选择器把 PC+2 送回来（Thumb 指令大多 2 字节）；"
                   "遇到跳转，控制单元把“跳转”线拉到 1，选择器改送跳转目标，程序就跳走了。\n\n"
                   "双击它，看寄存器内部的 D 触发器。", ("reg", 15)),
            "plus2": ("+2 加法器", "一个专门的小加法器，永远算 PC + 2，给“下一条指令”的地址做准备。", None),
            "pcmux": ("PC 选择器（多路选择器 MUX）",
                      "多路选择器：几个输入里挑一个送到输出，挑哪个由下面的选择线决定。\n"
                      "跳转线 = 0：选 PC+2（按顺序执行）\n跳转线 = 1：选跳转目标（if、循环、函数调用）", None),
            "amux": ("地址选择器",
                     "决定这次放到地址线上的是谁：\n取指线 = 1：放 PC（去 Flash 取下一条指令）\n"
                     "取指线 = 0：放 ALU 算出的地址（LDR、STR 读写变量）", None),
            "ir": ("IR 指令寄存器",
                   "取指时从数据线上收下机器码，存起来交给控制单元慢慢“看”。"
                   "真实的 Cortex-M3 有一条“流水线”，取指、译码、执行同时进行，这里简化成一条一条来。", None),
            "control": ("控制单元（指令译码器）",
                        "CPU 的“指挥”。它看 IR 里的机器码是哪条指令，然后拉高或拉低一根根控制线："
                        "取指、读 RD、写 WR、写寄存器、跳转……每根都是 1 位的线（绿色）。\n\n"
                        "它还看标志位 NZCV，决定条件跳转（BEQ、BLE……）跳不跳。", None),
            "regfile": ("寄存器组（R0~R15）",
                        "16 个 32 位寄存器，是 CPU 手边的“草稿格子”。它有两个读口 A、B（一次能同时读两个），"
                        "一个写口 WD（写回数据）+ WE（写使能）。\n\n双击进去看它怎么挑出要读写的那个寄存器。",
                        ("regfile", None)),
            "wbmux": ("写回选择器",
                      "写回寄存器的数从哪来：上面那路是 ALU 的计算结果（ADDS 之类），"
                      "下面那路是从数据线读回来的数（LDR 之类）。", None),
            "alu": ("ALU 算术逻辑单元",
                    "CPU 里真正做计算的电路：加、减、与、或、异或、移位、比较……\n"
                    "左边进来两个数 A、B，右边出来结果；结果的特点记进标志位 NZCV。\n\n"
                    "这里还让 ALU 顺便算读写数据的地址和跳转目标（真实芯片里有专门的小加法器）。\n\n"
                    "双击进去，看加法是怎么用一排全加器做出来的。", ("alu", None)),
            "flags": ("标志位 NZCV",
                      "程序状态寄存器（xPSR）里的 4 位，每一位是 1 根线：\n"
                      "· N：结果是负数    · Z：结果是 0\n· C：加法有进位（减法没有借位）\n"
                      "· V：有符号数溢出\n\n条件跳转就是让控制单元看这 4 根线决定跳不跳。", None),
        }

    def apply(self, st):
        w = self.w
        k = st.kind
        h = st.hold
        addr, data, rd, wr = st.bus()
        busy = st.now("fetch", "mem_read", "mem_write")
        pc = st.reg_value(15)
        self.pc_text.node().setText("0x%08X" % pc)
        self.net(w["pc"], pc, st.now("fetch"))
        self.net(w["pc2"], (pc + 2) & MASK, st.now("fetch"))
        branch = k == "branch" and st.beat.taken
        self.net(w["br"], int(branch), st.now("branch"))
        nxt = st.beat.target if branch else (pc + 2) & MASK
        self.net(w["pcin"], nxt, st.now("fetch", "branch"))
        self.net(w["fetch"], int(k == "fetch"))
        self.net(w["aout"], addr, busy)
        self.a_val.node().setText("")
        self.net(w["rd"], rd, busy and rd)
        self.net(w["wr"], wr, busy and wr)
        self.rd_val.node().setText(str(rd))
        self.wr_val.node().setText(str(wr))
        self.net(w["d"], data, busy)
        self.d_val.node().setText("")
        self.net(w["d_ir"], data, st.now("fetch"))
        self.net(w["d_load"], data, st.now("mem_read"))
        self.net(w["d_store"], data, st.now("mem_write"))
        if st.ir:
            code, size = st.ir
            self.ir_text.node().setText(("%08X" if size == 4 else "%04X") % code)
            self.net(w["ir"], code & 0xFFFF, st.now("fetch", "decode"))
        else:
            self.ir_text.node().setText("")
            self.net(w["ir"], None)
        self.ctrl_text.node().setText(st.asm)
        self.net(w["we"], int(k == "write_reg"), st.now("write_reg"))
        self.net(w["wd"], st.wd(), st.now("write_reg"))
        reads = st.reads()
        if k == "write_reg":
            self.rf_text.node().setText("写 %s" % REG_NAMES[st.beat.reg])
        elif reads:
            self.rf_text.node().setText("读 " + " ".join(REG_NAMES[r] for r in reads))
        else:
            self.rf_text.node().setText("")
        self.net(w["rfa"], h.get("rf_a"), st.now("read_reg"))
        self.net(w["rfb"], h.get("rf_b"), st.now("read_reg") and len(reads) > 1)
        self.net(w["y"], h.get("y"), st.now("alu", "branch", "mem_read", "mem_write", "calc"))
        alu = st.alu
        self.net(w["nzcv"], None if alu is None else
                 sum(alu.flags_new[f] << (3 - i) for i, f in enumerate("NZCV")),
                 st.now("alu"))
        for i, f in enumerate("NZCV"):
            v = st.flags[f]
            self.flag_text[i].node().setText("%s\n%d" % (f, v))
            self.flag_lines[3 - i].set(v, st.now("branch"))
        self.pc.set_active(st.now("fetch", "branch"))
        self.plus2.set_active(st.now("fetch"))
        self.pcmux.set_active(st.now("fetch", "branch"))
        self.amux.set_active(busy)
        self.ir.set_active(st.now("fetch", "decode"))
        self.ctrl.set_active(st.now("decode", "branch"))
        self.rf.set_active(st.now("read_reg", "write_reg"))
        self.wbmux.set_active(st.now("write_reg"))
        self.alu.set_active(st.now("alu", "calc"))
        self.flags_box.set_active(st.now("alu", "branch"))


# =====================================================================
# 第 3 层：寄存器组
# =====================================================================
def _rz(i):
    return 2 + (15 - i) * 2


class RegFileSheet(Sheet):
    key = "regfile"
    bounds = (-10, -2.5, 38, 36.5)

    def title(self):
        return "寄存器组"

    def build(self):
        c = self.c
        c.text("寄存器组：16 个寄存器 + 写选择译码器 + 读出选择器", -9.5, 35.8, 0.7)
        _, self.wd_val = c.pin_in(-2, 34, "WD 写入数据")
        self.wd = [c.wire([(-1.7, 34), (9, 34), (9, _rz(15) + 1.15)], 32,
                          probe=(-1.5, 34.4), prefix="")]
        _, self.wn_val = c.pin_in(-2, 20, "W# 写第几个")
        self.wn = c.wire([(-1.7, 20), (3, 20)], 4)
        _, self.we_val = c.pin_in(-2, 16, "WE 写使能")
        self.we = c.wire([(-1.7, 16), (3, 16)])
        self.dec = c.box(3, 1.4, 6, 34.6, "", tag="wdec")
        c.text("写\n选\n择\n译\n码\n器", 4.5, 26, 0.6, INK, "center")
        self.mux = c.box(21, 1.4, 25, 34.6, "", tag="rmux")
        c.text("读\n出\n选\n择\n器", 23, 26, 0.6, INK, "center")
        self.regs, self.reg_text, self.we_lines, self.q_lines = [], [], [], []
        for i in range(16):
            z = _rz(i)
            self.regs.append(c.box(10, z, 17, z + 1.6, "", tag="reg%d" % i))
            self.reg_text.append(c.text("", 10.3, z + 0.5, 0.55, INK))
            self.wd.append(c.wire([(9, z + 1.15), (10, z + 1.15)], 32))
            c.dot(9, z + 1.15)
            self.we_lines.append(c.wire([(6, z + 0.45), (10, z + 0.45)]))
            self.q_lines.append(c.wire([(17, z + 0.8), (21, z + 0.8)], 32))
        self.sel_a = c.wire([(22.3, -1.2), (22.3, 1.4)], 4, probe=(22.0, -2.1), prefix="读A选 ",
                            probe_align="right")
        self.sel_b = c.wire([(23.7, -1.2), (23.7, 1.4)], 4, probe=(24.0, -2.1), prefix="读B选 ")
        self.out_a = c.wire([(25, 24), (29, 24)], 32, probe=(25.3, 24.35))
        self.out_b = c.wire([(25, 12), (29, 12)], 32, probe=(25.3, 12.35))
        _, self.oa_val = c.pin_out(29.3, 24, "读口 A")
        _, self.ob_val = c.pin_out(29.3, 12, "读口 B")
        self.picks = {"reg%d" % i: (
            "寄存器 %s" % REG_NAMES[i],
            "一个 32 位寄存器。左边两根线：上面是写入数据 D，下面是这个寄存器自己的写使能 WE。"
            "只有它的 WE 是 1 时，时钟一跳，它才把 D 存进去。右边是它的输出 Q，一直送到读出选择器。\n\n"
            "双击进去，看它内部的 32 个 D 触发器。", ("reg", i)) for i in range(16)}
        self.picks["wdec"] = (
            "写选择译码器（4 线 - 16 线译码器）",
            "输入 W# 是 4 位二进制（0~15），说明这次写第几个寄存器。译码器有 16 根输出线，"
            "WE=1 时只把第 W# 根拉到 1，其余都是 0；WE=0 时 16 根全是 0，谁也不写。", None)
        self.picks["rmux"] = (
            "读出选择器（两个 16 选 1 多路选择器）",
            "16 个寄存器的输出都连到这里。下面的“读A选”“读B选”各是 4 位数，"
            "分别从 16 个里挑一个送到读口 A、读口 B。所以 ADDS R2, R0, R1 能在同一拍读出 R0 和 R1。", None)

    def apply(self, st):
        wd = st.wd()
        writing = st.kind == "write_reg"
        self.net(self.wd, wd, st.now("write_reg"))
        self.wd_val.node().setText(_short(wd))
        wn = st.beat.reg if writing else None
        self.wn.set(wn, st.now("write_reg"))
        self.wn_val.node().setText(_b(wn))
        self.we.set(int(writing), st.now("write_reg"))
        self.we_val.node().setText(str(int(writing)))
        reads = st.reads()
        for i in range(16):
            v = st.reg_value(i)
            self.reg_text[i].node().setText("%-3s 0x%08X" % (REG_NAMES[i], v))
            self.we_lines[i].set(int(writing and wn == i))
            self.q_lines[i].set(v, i in reads and st.active)
            self.regs[i].set_active(st.active and (i in reads or (writing and wn == i)))
        h = st.hold
        self.sel_a.set(h.get("sel_a"), st.now("read_reg"))
        self.sel_b.set(h.get("sel_b"), st.now("read_reg") and len(reads) > 1)
        self.out_a.set(h.get("rf_a"), st.now("read_reg"))
        self.out_b.set(h.get("rf_b"), st.now("read_reg") and len(reads) > 1)
        for txt, v in ((self.oa_val, h.get("rf_a")), (self.ob_val, h.get("rf_b"))):
            txt.node().setText(_short(v))
        self.dec.set_active(st.now("write_reg"))
        self.mux.set_active(st.now("read_reg"))


# =====================================================================
# 第 4 层：一个寄存器 = 32 个 D 触发器
# =====================================================================
def _dx(b):
    return 8 + (7 - b) * 4.1


class RegisterSheet(Sheet):
    key = "reg"
    bounds = (-12, -0.5, 48, 23.5)

    def title(self):
        return "寄存器 %s" % REG_NAMES[self.param]

    def build(self):
        c = self.c
        i = self.param
        name = REG_NAMES[i]
        c.text("%s：32 位寄存器 = 32 个 D 触发器并排。WE=1 时，CLK 从 0 跳到 1 的那一下把 D 存进去"
               % name, -11.5, 22.6, 0.6)
        src = "D 下一个 PC" if i == 15 else "D 写入数据"
        _, self.d_val = c.pin_in(-2, 20, src)
        self.d_rail = c.wire([(-1.7, 20), (40, 20)], 32, probe=(30.5, 20.35), prefix="D = ")
        self.q_rail = c.wire([(6, 16), (43.7, 16)], 32, probe=(30.5, 16.35), prefix="Q = ")
        _, self.q_val = c.pin_out(44, 16, "Q 输出")
        _, self.we_val = c.pin_in(-2, 4, "WE 写使能")
        _, self.clk_val = c.pin_in(-2, 1, "CLK 时钟")
        g = c.gate("AND", 3, 2.5, tag="and")
        self.we = c.wire([(-1.7, 4), (1.5, 4), (1.5, g.a[1]), g.a])
        self.clk = c.wire([(-1.7, 1), (1.5, 1), (1.5, g.b[1]), g.b])
        self.gclk = [c.wire([g.out, (38, 2.5)])]
        self.and_gate = g
        c.box(0.5, 7.5, 6, 13, "", fill=(0.95, 0.95, 0.95, 1))
        c.text("bit31 ~ bit8\n还有 24 个\n一样的触发器", 3.25, 11.6, 0.5, INK_DIM, "center")
        self.d_bits, self.q_bits, self.q_text, self.ffs = {}, {}, {}, {}
        for b in range(7, -1, -1):
            x = _dx(b)
            self.ffs[b] = c.box(x, 7.5, x + 2.6, 13, "", tag="dff%d" % b)
            c.text("bit%d" % b, x + 1.3, 13.3, 0.5, INK, "center")
            c.text("D", x + 0.2, 11.75, 0.53, INK)
            c.text("Q", x + 2.4, 11.75, 0.53, INK, "right")
            c.line([(x, 8.6), (x + 0.5, 9), (x, 9.4)], INK, 0.07)
            self.q_text[b] = c.text("0", x + 1.3, 9.6, 0.9, INK, "center")
            self.d_bits[b] = c.wire([(x - 0.6, 20), (x - 0.6, 12), (x, 12)])
            c.dot(x - 0.6, 20)
            self.gclk.append(c.wire([(x - 0.9, 2.5), (x - 0.9, 9), (x, 9)]))
            c.dot(x - 0.9, 2.5)
            self.q_bits[b] = c.wire([(x + 2.6, 12), (x + 3.1, 12), (x + 3.1, 16)])
            c.dot(x + 3.1, 16)
        c.text("与门：只有 WE 和 CLK 都是 1，触发器的时钟端才会跳到 1", 6, 0.38, 0.45, INK_DIM)
        self.picks = {"dff%d" % b: (
            "D 触发器（%s 的 bit%d）" % (name, b),
            "能记住 1 位的最小电路。D 是输入，Q 是输出，左下角的小三角是时钟输入。\n"
            "时钟从 0 跳到 1 的那一瞬间（上升沿），它把 D 的值存下来，从 Q 送出去；其他时候 D 怎么变，Q 都不变。\n\n"
            "双击进去，看它是怎么用与非门搭出来的。", ("dff", (i, b))) for b in range(8)}
        self.picks["and"] = ("与门 AND",
                             "两个输入都是 1，输出才是 1。这里用它把“写使能 WE”和“时钟 CLK”合起来："
                             "不写这个寄存器时，它的触发器根本收不到时钟，里面的值就不会变。\n"
                             "（真实芯片一般用选择器而不是直接“门控时钟”，道理一样。）", None)

    def apply(self, st):
        d, we, clk, g, q, w = reg_signals(st, self.param)
        act = st.active and w is not None
        self.d_rail.set(d, act)
        self.d_val.node().setText(_short(d))
        self.q_rail.set(q, act and clk)
        self.q_val.node().setText(_short(q))
        self.we.set(we, act)
        self.we_val.node().setText(str(we))
        self.clk.set(clk)
        self.clk_val.node().setText(str(clk))
        self.net(self.gclk, g, act)
        self.and_gate.shape.set_active(act)
        for b in range(8):
            self.d_bits[b].set(logic.bit(d, b), act)
            qb = q >> b & 1
            self.q_bits[b].set(qb)
            self.q_text[b].node().setText(str(qb))
            self.ffs[b].set_active(act)


def reg_signals(st, i):
    """寄存器 i 的输入输出：(D, WE, CLK, 触发器的时钟 = WE 与 CLK, Q, 这一拍写不写)。"""
    w = st.write_of(i)
    if i == 15:
        d = w[1] if w else (st.reg_value(15) + 2) & MASK
    else:
        d = st.wd()
    we = int(w is not None)
    return d, we, st.clk, logic.AND(we, st.clk), st.reg_value(i), w


# =====================================================================
# 第 5 层：一个 D 触发器 = 主锁存器 + 从锁存器（与非门）
# =====================================================================
class DFFSheet(Sheet):
    key = "dff"
    bounds = (-12, -1, 41, 20)

    def title(self):
        i, b = self.param
        return "%s 的 bit%d" % (REG_NAMES[i], b)

    def build(self):
        c = self.c
        i, b = self.param
        c.text("%s 的 bit%d：一个 D 触发器 = 两个“锁存器”串起来，用 8 个与非门 + 2 个非门搭成"
               % (REG_NAMES[i], b), -11.5, 19.2, 0.6)
        for x0, x1, text in ((4.5, 15.6, "主锁存器：C=0 时跟着 D 走"),
                             (20.6, 31.7, "从锁存器：C=1 时把主锁存器的值送到 Q")):
            c.line([(x0, 6.2), (x1, 6.2), (x1, 16.4), (x0, 16.4), (x0, 6.2)], INK_DIM, 0.05)
            c.text(text, (x0 + x1) / 2, 16.7, 0.5, INK_DIM, "center")
        _, self.d_val = c.pin_in(-2, 14.5, "D")
        _, self.c_val = c.pin_in(-2, 2, "C 时钟（WE 与 CLK）")
        G = {}
        G["notd"] = c.gate("NOT", 2.5, 7.5, tag="not")
        G["notc"] = c.gate("NOT", 3, 2, tag="not")
        G["n1"] = c.gate("NAND", 6, 14, tag="nand")
        G["n2"] = c.gate("NAND", 6, 8, tag="nand")
        G["m1"] = c.gate("NAND", 11, 13.5, tag="nand")
        G["m2"] = c.gate("NAND", 11, 8.5, tag="nand")
        G["n3"] = c.gate("NAND", 22, 14, tag="nand")
        G["n4"] = c.gate("NAND", 22, 8, tag="nand")
        G["s1"] = c.gate("NAND", 27, 13.5, tag="nand")
        G["s2"] = c.gate("NAND", 27, 8.5, tag="nand")
        self.G = G
        W = {}
        W["d"] = [c.wire([(-1.7, 14.5), G["n1"].a]), c.wire([(1.5, 14.5), (1.5, 7.5), G["notd"].a])]
        c.dot(1.5, 14.5)
        W["nd"] = [c.wire([G["notd"].out, G["n2"].b])]
        W["c"] = [c.wire([(-1.7, 2), G["notc"].a]),
                  c.wire([(2, 2), (2, 0.5), (20, 0.5), (20, 13.5), G["n3"].b]),
                  c.wire([(20, 8.5), G["n4"].a])]
        c.dot(2, 2)
        c.dot(20, 8.5)
        W["nc"] = [c.wire([G["notc"].out, (5, 2), (5, 13.5), G["n1"].b]),
                   c.wire([(5, 8.5), G["n2"].a])]
        c.dot(5, 8.5)
        W["sm"] = [c.wire([G["n1"].out, G["m1"].a])]
        W["rm"] = [c.wire([G["n2"].out, G["m2"].b])]
        W["qm"] = [c.wire([G["m1"].out, (18, 13.5), (18, 14.5), G["n3"].a]),
                   c.wire([(14.2, 13.5), (14.2, 11.2), (10, 11.2), (10, 9), G["m2"].a])]
        c.dot(14.2, 13.5)
        W["nqm"] = [c.wire([G["m2"].out, (18.6, 8.5), (18.6, 7.5), G["n4"].b]),
                    c.wire([(14.8, 8.5), (14.8, 10.6), (9.6, 10.6), (9.6, 13), G["m1"].b])]
        c.dot(14.8, 8.5)
        W["ss"] = [c.wire([G["n3"].out, G["s1"].a])]
        W["rs"] = [c.wire([G["n4"].out, G["s2"].b])]
        W["q"] = [c.wire([G["s1"].out, (35.4, 13.5)]),
                  c.wire([(30.2, 13.5), (30.2, 11.2), (26, 11.2), (26, 9), G["s2"].a])]
        c.dot(30.2, 13.5)
        W["nq"] = [c.wire([G["s2"].out, (35.4, 8.5)]),
                   c.wire([(30.8, 8.5), (30.8, 10.6), (25.6, 10.6), (25.6, 13), G["s1"].b])]
        c.dot(30.8, 8.5)
        _, self.q_val = c.pin_out(36, 13.5, "Q")
        _, self.nq_val = c.pin_out(36, 8.5, "Q非")
        c.text("Qm", 16.2, 13.8, 0.50, INK_DIM)
        self.W = W
        self.picks = {
            "nand": ("与非门 NAND",
                     "先“与”再取反：两个输入都是 1 时输出 0，其他情况输出 1。门的右边有个小圆圈，就表示“取反”。\n\n"
                     "两个与非门首尾交叉相连（一个的输出接另一个的输入），就能“记住”一个 0 或 1，"
                     "这叫锁存器。图里每个虚线框是一个锁存器。", None),
            "not": ("非门 NOT", "输出和输入相反：进 1 出 0，进 0 出 1。", None),
        }

    def apply(self, st):
        i, b = self.param
        d_word, we, clk, cgate, q_word, w = reg_signals(st, i)
        d = logic.bit(d_word, b)
        cc = cgate
        q_hold = q_word >> b & 1
        em = logic.NOT(cc)
        nd, sm, rm, qm, nqm = logic.latch(d, em, d)
        _, ss, rs, q, nq = logic.latch(qm, cc, q_hold)
        act = st.active and w is not None
        vals = {"d": d, "nd": nd, "c": cc, "nc": em, "sm": sm, "rm": rm, "qm": qm, "nqm": nqm,
                "ss": ss, "rs": rs, "q": q, "nq": nq}
        for k, v in vals.items():
            self.net(self.W[k], v)
        self.d_val.node().setText(_b(d))
        self.c_val.node().setText(_b(cc))
        self.q_val.node().setText(_b(q))
        self.nq_val.node().setText(_b(nq))
        for g in self.G.values():
            g.shape.set_active(act)


# =====================================================================
# 第 3 层：ALU = 一排全加器 + 逻辑单元 + 结果选择器
# =====================================================================
def _ax(b):
    return 6 + (7 - b) * 5


ADDER_OPS = ("+", "-", "pass")


def alu_signals(alu):
    """ALU 里加法器那一路的输入输出（逻辑运算时加法器也在算，只是结果没被选中）。"""
    if alu is None:
        return None
    sub = int(alu.op == "-")
    a = 0 if alu.op in ("pass", "~") else alu.a
    b = alu.b
    bp = (~b & MASK) if sub else b
    s, carries, cout, v = add_with_carry(a, bp, sub)
    return {"a": a, "b": b, "sub": sub, "bp": bp, "sum": s, "carries": carries, "cout": cout,
            "sel": 0 if alu.op in ADDER_OPS else 1, "y": alu.result}


class ALUSheet(Sheet):
    key = "alu"
    bounds = (-11, -2.2, 50, 33)

    def title(self):
        return "ALU"

    def build(self):
        c = self.c
        c.text("ALU：32 个一位全加器排成一排，进位从右往左传（这里画出最低 8 位）", -10.5, 32.3, 0.65)
        _, self.a_val = c.pin_in(-6, 31, "A")
        _, self.b_val = c.pin_in(-6, 28, "B")
        _, self.sub_val = c.pin_in(-6, 26.3, "减法 SUB")
        self.a_rail = c.wire([(-5.7, 31), (43, 31)], 32, probe=(-4, 31.35), prefix="A = ")
        self.b_rail = c.wire([(-5.7, 28), (43, 28)], 32, probe=(-4, 28.35), prefix="B = ")
        self.sub_rail = [c.wire([(-5.7, 26.3), (44.5, 26.3), (44.5, 14.5), (42.8, 14.5)])]
        self.a_bits, self.b_bits, self.bp_bits, self.c_lines, self.s_bits = {}, {}, {}, {}, {}
        self.sub_taps, self.fas, self.xors, self.fa_text = {}, {}, {}, {}
        for b in range(8):
            x = _ax(b)
            self.fas[b] = c.box(x - 1.8, 12, x + 1.8, 17, "", tag="fa%d" % b)
            c.text("全加器", x, 14.9, 0.5, INK, "center")
            c.text("bit%d" % b, x, 17.9, 0.53, INK_DIM, "center")
            self.fa_text[b] = c.text("", x, 12.4, 0.5, INK, "center")
            for name, px, pz, al in (("A", x - 1, 16.3, "center"), ("B'", x + 1, 16.3, "center"),
                                     ("S", x, 13.6, "center"), ("Ci", x + 1.65, 14.2, "right"),
                                     ("Co", x - 1.65, 14.2, "left")):
                c.text(name, px, pz, 0.44, INK_DIM, al)
            self.a_bits[b] = c.wire([(x - 1, 31), (x - 1, 17)])
            c.dot(x - 1, 31)
            g = c.gate("XOR", x + 1, 25, tag="xor", facing="down", size=0.75)
            self.xors[b] = g
            self.b_bits[b] = c.wire([(g.a[0], 28), g.a])
            c.dot(g.a[0], 28)
            self.sub_taps[b] = c.wire([(g.b[0], 26.3), g.b])
            c.dot(g.b[0], 26.3)
            self.bp_bits[b] = c.wire([g.out, (x + 1, 17)])
            self.s_bits[b] = c.wire([(x, 12), (x, 9)])
            c.dot(x, 9)
            # 进位：这一位的 Co 接到左边一位的 Ci
            self.c_lines[b + 1] = c.wire([(x - 1.8, 14.5), (x - 3.2 if b < 7 else 1.5, 14.5)])
        c.dot(44.5, 26.3)
        self.rest = c.box(-4, 12, 1.5, 17, "", tag="rest")
        c.text("bit8 ~ bit31\n还有 24 个\n全加器", -1.25, 15.9, 0.5, INK_DIM, "center")
        self.c_out = c.wire([(-4, 14.5), (-6.5, 14.5), (-6.5, 8)])
        c.text("最高位进位", -6.7, 14.8, 0.48, INK_DIM, "right")
        self.rest_s = c.wire([(-1.25, 12), (-1.25, 9)], 24)
        self.sum_rail = c.wire([(-1.25, 9), (43, 9), (43, 6.8), (44, 6.8)], 32,
                               probe=(28, 9.35), prefix="加法器结果 = ")
        self.logic = c.box(18, 3, 36, 7.2, "逻辑单元", tag="logicunit", title_size=0.6,
                           sub="与、或、异或、取反、移位、乘法（A、B 也接到这里）")
        self.logic_out = c.wire([(36, 5.2), (44, 5.2)], 32)
        self.ymux, ins, out, sel = c.mux(44, 6, 2, tag="ymux")
        self.y = c.wire([out, (47.7, 6)], 32, probe=(49.5, 3.4), prefix="Y = ",
                        probe_align="right")
        _, self.y_val = c.pin_out(48, 6, "结果 Y", label_side="top")
        self.sel = c.wire([(sel[0], 0.6), sel])
        self.sel_text = c.text("", sel[0], -0.5, 0.50, INK_DIM, "center")
        self.flagbox = c.box(-9, 1, 0, 8, "标志位逻辑", tag="flaglogic", title_size=0.55)
        c.text("N = 结果最高位\nZ = 结果全是 0\nC = 最高位进位\nV = 有符号溢出", -4.5, 5.6, 0.48,
               INK_DIM, "center")
        self.flag_pins = {}
        for k, f in enumerate("NZCV"):
            x = -8 + 2.2 * k
            self.flag_pins[f] = (c.wire([(x, 1), (x, -0.4)]), c.text("", x, -1.4, 0.55, INK, "center"))
        self.picks = {"fa%d" % b: (
            "一位全加器（bit%d）" % b,
            "把三个 1 位的数加起来：A 的这一位、B' 的这一位，再加上右边一位送来的进位 Ci。"
            "得到这一位的和 S，以及送给左边一位的进位 Co。\n\n"
            "32 个这样的全加器排成一排、进位一个传一个，就是 32 位加法器（叫“行波进位加法器”）。\n\n"
            "双击进去，看它是怎么用 5 个门搭出来的。", ("fa", b)) for b in range(8)}
        self.picks.update({
            "xor": ("异或门 XOR（做减法用）",
                    "两个输入不一样输出 1，一样输出 0。另一个输入接 SUB：\n"
                    "SUB=0 时 B' = B（原样通过）；SUB=1 时 B' = B 每一位取反。\n"
                    "做减法时 SUB=1，同时最右边一位的进位输入也是 1，"
                    "合起来就是 A + (~B) + 1 = A - B（补码）。", None),
            "rest": ("bit8 ~ bit31", "和右边画出来的 8 个全加器一模一样，只是太多了画不下。", None),
            "logicunit": ("逻辑单元",
                          "做按位与、或、异或、取反、移位、乘法的电路。它和加法器同时在算，"
                          "最后由右边的结果选择器挑一个当成 ALU 的结果。", None),
            "ymux": ("结果选择器",
                     "下面的选择线是 0：选加法器（加、减、比较、MOVS）；是 1：选逻辑单元。"
                     "控制单元根据指令决定选哪个。", None),
            "flaglogic": ("标志位逻辑",
                          "看结果算出 NZCV：N 就是结果的第 31 位；Z 是把 32 位全部“或”起来再取反；"
                          "C 是最高位的进位；V 看两个加数和结果的符号。", None),
        })

    def apply(self, st):
        s = alu_signals(st.alu)
        act = st.now("alu")
        if s is None:
            vals = None
        else:
            vals = s
        A = vals and vals["a"]
        B = vals and vals["b"]
        self.a_rail.set(A, act)
        self.b_rail.set(B, act)
        self.a_val.node().setText(_short(A))
        self.b_val.node().setText(_short(B))
        sub = vals and vals["sub"]
        self.net(self.sub_rail, sub, act and sub)
        self.sub_val.node().setText(_b(sub))
        for b in range(8):
            if vals is None:
                ab = bb = bpb = cin = cout = sb = None
            else:
                ab, bb, bpb = A >> b & 1, B >> b & 1, vals["bp"] >> b & 1
                cin = vals["carries"] >> b & 1
                cout = vals["carries"] >> (b + 1) & 1
                sb = vals["sum"] >> b & 1
            self.a_bits[b].set(ab)
            self.b_bits[b].set(bb)
            self.sub_taps[b].set(sub)
            self.bp_bits[b].set(bpb)
            self.s_bits[b].set(sb)
            self.c_lines[b + 1].set(cout)
            self.fa_text[b].node().setText("" if vals is None else "%s+%s+%s" % (ab, bpb, cin))
            self.fas[b].set_active(act)
            self.xors[b].shape.set_active(act and sub == 1)
        self.c_out.set(None if vals is None else vals["cout"])
        self.rest_s.set(None if vals is None else vals["sum"] >> 8, False)
        self.sum_rail.set(None if vals is None else vals["sum"], act and vals["sel"] == 0)
        lo = None if vals is None else (st.alu.result if vals["sel"] == 1 else None)
        self.logic_out.set(lo, act and lo is not None)
        y = None if vals is None else vals["y"]
        self.y.set(y, act)
        self.y_val.node().setText(_short(y))
        sel = None if vals is None else vals["sel"]
        self.sel.set(sel, act)
        self.sel_text.node().setText("" if sel is None else
                                     ("选加法器" if sel == 0 else "选逻辑单元"))
        self.logic.set_active(act and sel == 1)
        self.ymux.set_active(act)
        self.flagbox.set_active(act and st.alu.set_flags)
        for f, (wire, txt) in self.flag_pins.items():
            v = None if st.alu is None else st.alu.flags_new[f]
            wire.set(v)
            txt.node().setText("%s=%s" % (f, _b(v)))


# =====================================================================
# 第 4 层：一位全加器 = 2 个异或门 + 2 个与门 + 1 个或门
# =====================================================================
class FullAdderSheet(Sheet):
    key = "fa"
    bounds = (-11, -1, 46, 19.5)

    def title(self):
        return "bit%d 全加器" % self.param

    def build(self):
        c = self.c
        b = self.param
        c.text("bit%d 的全加器：S = A ⊕ B' ⊕ Ci，Co = A·B' + (A ⊕ B')·Ci" % b, -10.5, 18.8, 0.65)
        _, self.a_val = c.pin_in(-1, 15, "A（第 %d 位）" % b)
        _, self.b_val = c.pin_in(-1, 11, "B'（第 %d 位）" % b)
        _, self.c_val = c.pin_in(-1, 4, "Ci 右边送来的进位")
        G = {"x1": c.gate("XOR", 6, 13, tag="xor"), "a1": c.gate("AND", 6, 8, tag="and"),
             "x2": c.gate("XOR", 14, 12.5, tag="xor"), "a2": c.gate("AND", 14, 5.5, tag="and"),
             "o": c.gate("OR", 20, 7, tag="or")}
        self.G = G
        W = {}
        W["a"] = [c.wire([(-0.7, 15), (2, 15), (2, 13.5), G["x1"].a]),
                  c.wire([(2, 13.5), (2, 8.5), G["a1"].a])]
        c.dot(2, 13.5)
        W["b"] = [c.wire([(-0.7, 11), (3.5, 11), (3.5, 12.5), G["x1"].b]),
                  c.wire([(3.5, 11), (3.5, 7.5), G["a1"].b])]
        c.dot(3.5, 11)
        W["p"] = [c.wire([G["x1"].out, (10, 13), G["x2"].a]),
                  c.wire([(10, 13), (10, 6), G["a2"].a])]
        c.dot(10, 13)
        W["cin"] = [c.wire([(-0.7, 4), (12, 4), (12, 12), G["x2"].b]),
                    c.wire([(12, 5), G["a2"].b])]
        c.dot(12, 5)
        W["g"] = [c.wire([G["a1"].out, (18, 8), (18, 7.5), G["o"].a])]
        W["t"] = [c.wire([G["a2"].out, (19, 5.5), (19, 6.5), G["o"].b])]
        W["s"] = [c.wire([G["x2"].out, (25.7, 12.5)])]
        W["cout"] = [c.wire([G["o"].out, (25.7, 7)])]
        self.W = W
        _, self.s_val = c.pin_out(26, 12.5, "S 这一位的和")
        _, self.co_val = c.pin_out(26, 7, "Co 送给左边的进位")
        c.text("P", 9.3, 13.3, 0.50, INK_DIM)
        c.text("G", 16.5, 8.3, 0.50, INK_DIM)
        c.text("T", 17, 5.8, 0.50, INK_DIM)
        self.table = c.text("", 34, 16.5, 0.55, INK)
        self.picks = {
            "xor": ("异或门 XOR", "两个输入不一样输出 1，一样输出 0。一位二进制加法的“和”（不管进位）正好就是异或：\n"
                    "0+0=0，0+1=1，1+0=1，1+1=10（本位是 0）。", None),
            "and": ("与门 AND", "两个输入都是 1，输出才是 1。A 和 B' 都是 1 时一定要进位，这就是上面那个与门 G。", None),
            "or": ("或门 OR", "有一个输入是 1，输出就是 1。两种情况会进位：A、B' 都是 1（G），"
                   "或者 A、B' 只有一个是 1 而且右边送来了进位（T）。", None),
        }

    def apply(self, st):
        b = self.param
        s = alu_signals(st.alu)
        if s is None:
            a = bp = cin = None
        else:
            a, bp, cin = s["a"] >> b & 1, s["bp"] >> b & 1, s["carries"] >> b & 1
        p, sm, g, t, co = logic.full_adder(a, bp, cin)
        act = st.now("alu")
        for k, v in {"a": a, "b": bp, "cin": cin, "p": p, "s": sm, "g": g, "t": t,
                     "cout": co}.items():
            self.net(self.W[k], v)
        for txt, v in ((self.a_val, a), (self.b_val, bp), (self.c_val, cin), (self.s_val, sm),
                       (self.co_val, co)):
            txt.node().setText(_b(v))
        for gate in self.G.values():
            gate.shape.set_active(act)
        rows = ["真值表", "A  B' Ci │ S  Co"]
        for k in range(8):
            ra, rb, rc = k >> 2 & 1, k >> 1 & 1, k & 1
            total = ra + rb + rc
            line = "%d  %d  %d  │ %d  %d" % (ra, rb, rc, total & 1, total >> 1)
            if (ra, rb, rc) == (a, bp, cin):
                line = "\1hi\1%s  ← 现在\2" % line
            rows.append(line)
        self.table.node().setText("\n".join(rows))


SHEETS = {cls.key: cls for cls in (ChipSheet, CPUSheet, RegFileSheet, RegisterSheet, DFFSheet,
                                   ALUSheet, FullAdderSheet)}
