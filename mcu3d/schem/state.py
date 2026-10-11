"""电路图要显示的“此刻每根线上是什么”。

模拟器（sim/view.py）每播放一拍，就把当前状态整理成一个 State 交给电路图。
电路图只看 State，不直接碰 CPU，所以以后把外设接进来也只要往这里加东西。

时钟的约定：每一拍的前半拍 CLK=0，数据先准备好；后半拍 CLK=1，
寄存器（D 触发器）在 CLK 从 0 变 1 的那一下（上升沿）把数据存进去。
"""

from ..sim.machine import region_of

BUS_KINDS = ("fetch", "mem_read", "mem_write")


class State:
    def __init__(self, beat=None, active=False, clk=0, regs=None, flags=None,
                 need_reset=False, alu=None, ir=None, asm="", hold=None):
        self.beat = beat            # 正在显示的这一拍（没有就是 None）
        self.active = active        # 这一拍是不是正在播放（播完了就 False，但值还留着）
        self.clk = clk
        self.regs = regs or [0] * 16
        self.flags = flags or {"N": 0, "Z": 0, "C": 0, "V": 0}
        self.need_reset = need_reset
        self.alu = alu              # 最近一次 ALU 运算的那一拍
        self.ir = ir                # 最近取到的机器码 (code, size)
        self.asm = asm              # 译码出来的汇编
        self.hold = hold or {}      # CPU 内部各条线最后一次的值：rf_a rf_b sel_a sel_b y

    @property
    def kind(self):
        return self.beat.kind if self.beat is not None else None

    def now(self, *kinds):
        """这一拍是不是这几种之一，并且正在播放。"""
        return self.active and self.kind in kinds

    # ---- 系统总线 ----
    def bus(self):
        """(地址, 数据, 读, 写)。没有访问时地址线、数据线没人驱动，是悬空的。"""
        b = self.beat
        if self.kind in BUS_KINDS:
            return b.addr, b.value, int(b.kind != "mem_write"), int(b.kind == "mem_write")
        return None, None, 0, 0

    def region(self):
        addr = self.bus()[0]
        if addr is None:
            return None
        return region_of(addr) or "periph"

    # ---- 寄存器 ----
    def write_of(self, i):
        """这一拍要不要写寄存器 i：返回 (旧值, 新值)，不写返回 None。"""
        b, k = self.beat, self.kind
        if k == "write_reg" and b.reg == i:
            return b.old, b.new
        if i == 15 and k == "fetch":
            return b.addr, b.next_pc
        if i == 15 and k == "branch" and b.taken:
            return b.old_pc, b.target
        return None

    def reg_value(self, i):
        """寄存器 i 输出端 Q 上的值：写入的那一拍，时钟上升沿之前还是旧值。"""
        w = self.write_of(i)
        if w is not None:
            return w[1] if self.clk else w[0]
        return self.regs[i]

    def wd(self):
        """寄存器组的“写入数据”总线：只有写回那一拍才有人驱动。"""
        if self.kind == "write_reg":
            return self.beat.new
        return None

    def reads(self):
        """这一拍从寄存器组读哪几个寄存器。"""
        if self.kind == "read_reg":
            return list(self.beat.regs)
        return []
