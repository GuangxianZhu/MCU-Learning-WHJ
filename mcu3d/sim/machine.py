"""芯片内部模拟器的“硬件”：存储器、总线和 CPU。

CPU 真的从 Flash 里取出 16 位机器码、自己译码、自己执行，不是按剧本演的。
每执行一条指令，step() 返回这条指令分成的若干“拍”（Beat），
画面按拍播放：取指 → 译码 → 读寄存器 → ALU 运算 → 访问存储器 → 写回。

地址按 STM32F103（ARM Cortex-M3）：
    Flash 0x0800 0000 起    SRAM 0x2000 0000 起（20KB）    外设 0x4000 0000 起
"""

from .asm import COND_NAMES, REG_NAMES

FLASH_BASE = 0x08000000
FLASH_SIZE = 0x1000
SRAM_BASE = 0x20000000
SRAM_SIZE = 0x5000
STACK_TOP = SRAM_BASE + SRAM_SIZE
PERIPH_BASE = 0x40000000
MASK = 0xFFFFFFFF

SP, LR, PC = 13, 14, 15


def region_of(addr):
    if FLASH_BASE <= addr < FLASH_BASE + FLASH_SIZE:
        return "flash"
    if SRAM_BASE <= addr < SRAM_BASE + SRAM_SIZE:
        return "sram"
    if PERIPH_BASE <= addr < 0x60000000:
        return "periph"
    return None


REGION_NAMES = {"flash": "Flash", "sram": "SRAM", "periph": "外设", None: "空地址"}


def hex32(v):
    return "0x%04X %04X" % (v >> 16 & 0xFFFF, v & 0xFFFF)


class Fault(Exception):
    """访问了不存在的地址等错误。真实芯片会进入 HardFault。"""


class Beat:
    """一拍：画面上的一个小步骤。kind 决定画面怎么演，text 是给人看的说明。"""

    def __init__(self, kind, text, **data):
        self.kind = kind
        self.text = text
        self.__dict__.update(data)

    def __repr__(self):
        return "<Beat %s %s>" % (self.kind, self.text)


class Bus:
    """系统总线：按地址把读写送到 Flash、SRAM 或外设。"""

    def __init__(self):
        self.flash = bytearray(FLASH_SIZE)
        self.sram = bytearray(SRAM_SIZE)
        self.devices = []          # (起始地址, 长度, 设备)，设备有 read/write(offset, size, value)

    def add_device(self, base, size, device):
        self.devices.append((base, size, device))

    def _locate(self, addr, size):
        if FLASH_BASE <= addr and addr + size <= FLASH_BASE + FLASH_SIZE:
            return self.flash, addr - FLASH_BASE
        if SRAM_BASE <= addr and addr + size <= SRAM_BASE + SRAM_SIZE:
            return self.sram, addr - SRAM_BASE
        return None, None

    def read(self, addr, size=4):
        if size > 1 and addr % size:
            raise Fault("地址 %s 没有对齐（%d 字节的读写，地址要是 %d 的倍数）"
                        % (hex32(addr), size, size))
        mem, off = self._locate(addr, size)
        if mem is not None:
            return int.from_bytes(mem[off:off + size], "little")
        for base, length, dev in self.devices:
            if base <= addr < base + length:
                return dev.read(addr - base, size) & ((1 << 8 * size) - 1)
        raise Fault("地址 %s 上什么都没有" % hex32(addr))

    def write(self, addr, value, size=4):
        if size > 1 and addr % size:
            raise Fault("地址 %s 没有对齐" % hex32(addr))
        value &= (1 << 8 * size) - 1
        mem, off = self._locate(addr, size)
        if mem is self.flash:
            raise Fault("Flash 在程序运行时不能直接写（地址 %s）" % hex32(addr))
        if mem is not None:
            mem[off:off + size] = value.to_bytes(size, "little")
            return
        for base, length, dev in self.devices:
            if base <= addr < base + length:
                dev.write(addr - base, size, value)
                return
        raise Fault("地址 %s 上什么都没有" % hex32(addr))

    def peek(self, addr, size=4):
        """给画面用的读：不触发外设副作用，读不到返回 None。"""
        try:
            mem, off = self._locate(addr, size)
            if mem is not None:
                return int.from_bytes(mem[off:off + size], "little")
            for base, length, dev in self.devices:
                if base <= addr < base + length:
                    peek = getattr(dev, "peek", dev.read)
                    return peek(addr - base, size)
        except Exception:
            return None
        return None


def add_with_carry(a, b, carry_in):
    """32 位加法，返回 (结果, 每一位的进位输入, C, V)。和 ALU 里一位一位算的完全一样。"""
    carries = 0
    c = carry_in
    res = 0
    for i in range(32):
        if c:
            carries |= 1 << i
        x = (a >> i) & 1
        y = (b >> i) & 1
        s = x ^ y ^ c
        c = (x & y) | (x & c) | (y & c)
        res |= s << i
    v = ((a ^ res) & (b ^ res)) >> 31 & 1
    return res, carries, c, v


def cond_passed(cond, f):
    n, z, c, v = f["N"], f["Z"], f["C"], f["V"]
    return [z == 1, z == 0, c == 1, c == 0, n == 1, n == 0, v == 1, v == 0,
            c == 1 and z == 0, c == 0 or z == 1, n == v, n != v,
            z == 0 and n == v, z == 1 or n != v][cond]


COND_TEXT = ["相等（Z=1）", "不相等（Z=0）", "无符号大于等于（C=1）", "无符号小于（C=0）",
             "是负数（N=1）", "不是负数（N=0）", "溢出（V=1）", "没溢出（V=0）",
             "无符号大于", "无符号小于等于", "有符号大于等于（N=V）", "有符号小于（N≠V）",
             "有符号大于（Z=0 且 N=V）", "有符号小于等于（Z=1 或 N≠V）"]


class CPU:
    def __init__(self, bus):
        self.bus = bus
        self.r = [0] * 16
        self.flags = {"N": 0, "Z": 0, "C": 0, "V": 0}
        self.need_reset = True
        self.count = 0

    # ---------------------------------------------------------------- 复位
    def reset(self):
        self.r = [0] * 16
        self.flags = {"N": 0, "Z": 0, "C": 0, "V": 0}
        self.need_reset = True
        self.count = 0

    def _reset_beats(self):
        sp = self.bus.read(FLASH_BASE)
        pc = self.bus.read(FLASH_BASE + 4)
        beats = [
            Beat("mem_read", "复位：CPU 自动从 Flash 的第 0 个字（向量表）读出栈顶地址",
                 addr=FLASH_BASE, size=4, value=sp),
            Beat("write_reg", "放进 SP（栈指针）", reg=SP, old=self.r[SP], new=sp),
            Beat("mem_read", "再读第 1 个字：复位后第一条指令的地址（最低位 1 表示 Thumb 指令）",
                 addr=FLASH_BASE + 4, size=4, value=pc),
            Beat("write_reg", "放进 PC，程序从这里开始执行", reg=PC, old=self.r[PC],
                 new=pc & ~1),
        ]
        self.r[SP] = sp
        self.r[PC] = pc & ~1
        self.need_reset = False
        return beats

    # ---------------------------------------------------------------- 执行
    def step(self):
        """执行一条指令，返回这条指令的所有拍。出错时最后一拍 kind='fault'。"""
        beats = []
        try:
            if self.need_reset:
                return self._reset_beats()
            self._step(beats)
            self.count += 1
        except Fault as e:
            beats.append(Beat("fault", "出错了：%s。真实芯片会跳进 HardFault 错误处理函数。" % e))
        return beats

    def _set_reg(self, beats, rd, value, text=None):
        value &= MASK
        beats.append(Beat("write_reg", text or "结果写回 %s" % REG_NAMES[rd],
                          reg=rd, old=self.r[rd], new=value))
        self.r[rd] = value

    def _alu(self, beats, op, a, b, text, set_flags=True, logic=False, shift_c=None):
        """ALU 做一次运算并更新标志位。返回结果。"""
        old = dict(self.flags)
        carries = None
        carry_in = 0
        shown_b = b
        if op in ("+", "-"):
            if op == "-":
                shown_b = ~b & MASK
                carry_in = 1
            res, carries, c, v = add_with_carry(a, shown_b, carry_in)
            if set_flags:
                self.flags.update(C=c, V=v)
        elif op == "&":
            res = a & b
        elif op == "|":
            res = a | b
        elif op == "^":
            res = a ^ b
        elif op == "&~":
            res = a & ~b & MASK
        elif op == "~":
            res = ~b & MASK
        elif op == "*":
            res = (a * b) & MASK
        elif op == "pass":
            res = b
        elif op == "<<":
            res = (a << b) & MASK
        elif op == ">>":
            res = (a >> b) & MASK
        else:
            raise ValueError(op)
        if set_flags:
            self.flags["N"] = res >> 31 & 1
            self.flags["Z"] = int(res == 0)
            if shift_c is not None:
                self.flags["C"] = shift_c
        beats.append(Beat("alu", text, op=op, a=a, b=b, b_shown=shown_b,
                          carry_in=carry_in, carries=carries, result=res,
                          flags_old=old, flags_new=dict(self.flags), set_flags=set_flags))
        return res

    def _read_regs(self, beats, regs, text=None):
        names = "、".join(REG_NAMES[r] for r in regs)
        vals = "，".join("%s=%s" % (REG_NAMES[r], show_value(self.r[r])) for r in regs)
        beats.append(Beat("read_reg", text or "从寄存器组读出 %s（%s）" % (names, vals),
                          regs=list(regs)))

    def _mem_read(self, beats, addr, size, text):
        value = self.bus.read(addr, size)
        beats.append(Beat("mem_read", text, addr=addr, size=size, value=value))
        return value

    def _mem_write(self, beats, addr, value, size, text):
        old = self.bus.peek(addr, size)
        self.bus.write(addr, value, size)
        beats.append(Beat("mem_write", text, addr=addr, size=size,
                          value=value & ((1 << 8 * size) - 1), old=old))

    def _step(self, beats):
        r = self.r
        pc = r[PC]
        hw = self.bus.read(pc, 2)
        size = 4 if hw >> 11 in (0b11101, 0b11110, 0b11111) else 2
        code = hw
        if size == 4:
            hw2 = self.bus.read(pc + 2, 2)
            code = hw << 16 | hw2
        d = decode(hw, hw2 if size == 4 else None, pc)
        beats.append(Beat("fetch", "取指：按 PC 的地址 %s 从 Flash 读出机器码 %s，PC 自动加 %d"
                          % (hex32(pc), ("%08X" if size == 4 else "%04X") % code, size),
                          addr=pc, size=size, value=code, next_pc=pc + size))
        beats.append(Beat("decode", "译码：%s —— %s" % (d.text, d.desc), asm=d.text,
                          desc=d.desc))
        r[PC] = pc + size
        self._execute(d, beats, pc)

    def _execute(self, d, beats, pc):
        r, f = self.r, self.flags
        op = d.op
        rd, rn, rm, imm = d.rd, d.rn, d.rm, d.imm
        if op == "NOP":
            beats.append(Beat("idle", "什么也不做，只花掉一拍"))
        elif op == "MOVS_IMM":
            res = self._alu(beats, "pass", 0, imm, "立即数 %d 原样穿过 ALU（顺便更新 N、Z 标志）" % imm)
            self._set_reg(beats, rd, res)
        elif op in ("ADDS", "SUBS", "CMP"):
            regs = [rn] + ([rm] if rm is not None else [])
            self._read_regs(beats, regs)
            b = r[rm] if rm is not None else imm
            sym = "-" if op in ("SUBS", "CMP") else "+"
            what = ("比较：算 %d - %d，只看结果设置标志位，结果不保存" % (_signed(r[rn]), _signed(b))
                    if op == "CMP" else "ALU 计算 %d %s %d" % (_signed(r[rn]), sym, _signed(b)))
            res = self._alu(beats, sym, r[rn], b, what)
            if op != "CMP":
                self._set_reg(beats, rd, res)
        elif op in ("ANDS", "ORRS", "EORS", "BICS", "MULS"):
            self._read_regs(beats, [rd, rm])
            sym = {"ANDS": "&", "ORRS": "|", "EORS": "^", "BICS": "&~", "MULS": "*"}[op]
            name = {"ANDS": "按位与", "ORRS": "按位或", "EORS": "按位异或",
                    "BICS": "按位清除", "MULS": "乘法"}[op]
            res = self._alu(beats, sym, r[rd], r[rm], "ALU 做%s" % name)
            self._set_reg(beats, rd, res)
        elif op == "MVNS":
            self._read_regs(beats, [rm])
            res = self._alu(beats, "~", 0, r[rm], "ALU 把每一位取反")
            self._set_reg(beats, rd, res)
        elif op in ("LSLS", "LSRS"):
            self._read_regs(beats, [rm])
            a = r[rm]
            if op == "LSLS":
                if imm == 0:
                    res = self._alu(beats, "pass", 0, a, "%s 的值原样穿过 ALU（相当于复制，顺便更新 N、Z）"
                                    % REG_NAMES[rm])
                else:
                    res = self._alu(beats, "<<", a, imm, "ALU 把 %s 左移 %d 位" % (REG_NAMES[rm], imm),
                                    shift_c=a >> (32 - imm) & 1)
            else:
                n = imm or 32
                res = self._alu(beats, ">>", a, n, "ALU 把 %s 右移 %d 位" % (REG_NAMES[rm], n),
                                shift_c=a >> (n - 1) & 1)
            self._set_reg(beats, rd, res)
        elif op in ("LDR", "STR", "LDRB", "STRB", "LDR_SP", "STR_SP"):
            base = SP if op.endswith("_SP") else rn
            size = 1 if op.endswith("B") else 4
            regs = [base] + ([rd] if op.startswith("STR") else [])
            self._read_regs(beats, regs)
            addr = (r[base] + imm) & MASK
            if imm:
                beats.append(Beat("calc", "算地址：%s + %d = %s" % (REG_NAMES[base], imm,
                                                               hex32(addr))))
            if op.startswith("LDR"):
                v = self._mem_read(beats, addr, size, "经总线读 %s（%s）"
                                   % (hex32(addr), REGION_NAMES[region_of(addr)]))
                self._set_reg(beats, rd, v, "读到的数放进 %s" % REG_NAMES[rd])
            else:
                self._mem_write(beats, addr, r[rd], size, "经总线把 %s 的值写到 %s（%s）"
                                % (REG_NAMES[rd], hex32(addr), REGION_NAMES[region_of(addr)]))
        elif op == "LDR_LIT":
            addr = ((pc + 4) & ~3) + imm
            v = self._mem_read(beats, addr, 4, "从程序后面的“文字池”读一个常数（也在 Flash 里，地址 %s）"
                               % hex32(addr))
            self._set_reg(beats, rd, v, "放进 %s" % REG_NAMES[rd])
        elif op in ("ADD_SP", "SUB_SP"):
            self._read_regs(beats, [SP])
            sym = "+" if op == "ADD_SP" else "-"
            res = self._alu(beats, sym, r[SP], imm, "调整栈指针：SP %s %d" % (sym, imm),
                            set_flags=False)
            self._set_reg(beats, SP, res)
        elif op == "PUSH":
            regs = d.regs
            self._read_regs(beats, [SP] + regs)
            new_sp = (r[SP] - 4 * len(regs)) & MASK
            self._set_reg(beats, SP, new_sp, "SP 先减 %d（栈往低地址长，留出 %d 个格子）"
                          % (4 * len(regs), len(regs)))
            for k, reg in enumerate(regs):
                self._mem_write(beats, new_sp + 4 * k, r[reg], 4, "把 %s 存进栈 %s"
                                % (REG_NAMES[reg], hex32(new_sp + 4 * k)))
        elif op == "POP":
            regs = d.regs
            self._read_regs(beats, [SP])
            sp = r[SP]
            vals = []
            for k, reg in enumerate(regs):
                vals.append(self._mem_read(beats, sp + 4 * k, 4, "从栈 %s 取回一个数"
                                           % hex32(sp + 4 * k)))
            self._set_reg(beats, SP, sp + 4 * len(regs), "SP 加 %d，这些格子用完了"
                          % (4 * len(regs)))
            for reg, v in zip(regs, vals):
                if reg == PC:
                    beats.append(Beat("branch", "取回的返回地址放进 PC：回到调用的地方",
                                      taken=True, old_pc=r[PC], target=v & ~1))
                    r[PC] = v & ~1
                else:
                    self._set_reg(beats, reg, v, "恢复 %s" % REG_NAMES[reg])
        elif op == "B":
            target = (pc + 4 + imm) & MASK
            beats.append(Beat("branch", "跳转：PC 改成 %s" % hex32(target), taken=True,
                              old_pc=r[PC], target=target))
            r[PC] = target
        elif op == "BCOND":
            target = (pc + 4 + imm) & MASK
            ok = cond_passed(d.cond, f)
            fl = " ".join("%s=%d" % (k, f[k]) for k in "NZCV")
            if ok:
                text = "看标志位（%s）：条件“%s”成立，跳到 %s" % (fl, COND_TEXT[d.cond], hex32(target))
            else:
                text = "看标志位（%s）：条件“%s”不成立，不跳，接着执行下一条" % (fl, COND_TEXT[d.cond])
            beats.append(Beat("branch", text, taken=ok, old_pc=r[PC], target=target,
                              cond=d.cond))
            if ok:
                r[PC] = target
        elif op == "BL":
            target = (pc + 4 + imm) & MASK
            self._set_reg(beats, LR, r[PC] | 1, "把返回地址 %s 存进 LR（最低位 1 表示 Thumb）"
                          % hex32(r[PC]))
            beats.append(Beat("branch", "跳到函数 %s" % hex32(target), taken=True,
                              old_pc=r[PC], target=target))
            r[PC] = target
        elif op == "BX":
            self._read_regs(beats, [rm])
            target = r[rm] & ~1
            beats.append(Beat("branch", "PC 改成 %s 里的地址 %s：函数返回"
                              % (REG_NAMES[rm], hex32(target)), taken=True,
                              old_pc=r[PC], target=target))
            r[PC] = target
        else:
            raise Fault("不认识的指令 %s" % op)


def show_value(v):
    """小数字用十进制，地址这种大数字用十六进制。"""
    s = _signed(v)
    return str(s) if -100000 < s < 100000 else hex32(v)


def _signed(v):
    return v - (1 << 32) if v & 0x80000000 else v


class Decoded:
    def __init__(self, op, text, desc, rd=None, rn=None, rm=None, imm=0, regs=None,
                 cond=None):
        self.op, self.text, self.desc = op, text, desc
        self.rd, self.rn, self.rm, self.imm = rd, rn, rm, imm
        self.regs = regs or []
        self.cond = cond


def _rl(regs):
    return "{%s}" % ", ".join(REG_NAMES[r] for r in regs)


def decode(hw, hw2, pc):
    """把机器码拆开，认出是哪条指令。这就是 CPU 里“指令译码器”做的事。"""
    R = REG_NAMES
    lo3 = hw & 7
    mid3 = hw >> 3 & 7
    if hw == 0xBF00:
        return Decoded("NOP", "NOP", "空操作")
    if hw >> 11 == 0b00100:
        rd, imm = hw >> 8 & 7, hw & 0xFF
        return Decoded("MOVS_IMM", "MOVS %s, #%d" % (R[rd], imm),
                       "把数字 %d 放进 %s" % (imm, R[rd]), rd=rd, imm=imm)
    if hw >> 11 in (0b00000, 0b00001):
        imm = hw >> 6 & 0x1F
        lsr = hw >> 11 == 1
        if not lsr and imm == 0:
            return Decoded("LSLS", "MOVS %s, %s" % (R[lo3], R[mid3]),
                           "把 %s 复制到 %s" % (R[mid3], R[lo3]), rd=lo3, rm=mid3, imm=0)
        name = "LSRS" if lsr else "LSLS"
        return Decoded(name, "%s %s, %s, #%d" % (name, R[lo3], R[mid3], imm or 32),
                       "把 %s %s移 %d 位，放进 %s" % (R[mid3], "右" if lsr else "左", imm or 32,
                                              R[lo3]), rd=lo3, rm=mid3, imm=imm)
    if hw >> 9 in (0b0001100, 0b0001101):
        sub = hw >> 9 & 1
        rm = hw >> 6 & 7
        name = "SUBS" if sub else "ADDS"
        return Decoded(name, "%s %s, %s, %s" % (name, R[lo3], R[mid3], R[rm]),
                       "%s %s %s，结果放进 %s，并更新标志位" % (R[mid3], "减" if sub else "加", R[rm],
                                                    R[lo3]), rd=lo3, rn=mid3, rm=rm)
    if hw >> 9 in (0b0001110, 0b0001111):
        sub = hw >> 9 & 1
        imm = hw >> 6 & 7
        name = "SUBS" if sub else "ADDS"
        return Decoded(name, "%s %s, %s, #%d" % (name, R[lo3], R[mid3], imm),
                       "%s %s %d，结果放进 %s，并更新标志位" % (R[mid3], "减" if sub else "加", imm,
                                                    R[lo3]), rd=lo3, rn=mid3, imm=imm)
    if hw >> 11 in (0b00101, 0b00110, 0b00111):
        rd, imm = hw >> 8 & 7, hw & 0xFF
        kind = hw >> 11 & 3
        if kind == 1:
            return Decoded("CMP", "CMP %s, #%d" % (R[rd], imm),
                           "比较 %s 和 %d（做减法，只设置标志位）" % (R[rd], imm), rn=rd, imm=imm)
        name = "ADDS" if kind == 2 else "SUBS"
        return Decoded(name, "%s %s, #%d" % (name, R[rd], imm),
                       "%s %s %d，并更新标志位" % (R[rd], "加" if kind == 2 else "减", imm),
                       rd=rd, rn=rd, imm=imm)
    if hw >> 6 == 0b0100001010:
        return Decoded("CMP", "CMP %s, %s" % (R[lo3], R[mid3]),
                       "比较 %s 和 %s（做减法，只设置标志位）" % (R[lo3], R[mid3]),
                       rn=lo3, rm=mid3)
    alu = {0b0100000000: ("ANDS", "按位与"), 0b0100000001: ("EORS", "按位异或"),
           0b0100001100: ("ORRS", "按位或"), 0b0100001110: ("BICS", "按位清除"),
           0b0100001111: ("MVNS", "按位取反"), 0b0100001101: ("MULS", "相乘")}
    if hw >> 6 in alu:
        name, what = alu[hw >> 6]
        if name == "MVNS":
            return Decoded(name, "MVNS %s, %s" % (R[lo3], R[mid3]),
                           "把 %s 每一位取反，放进 %s" % (R[mid3], R[lo3]), rd=lo3, rm=mid3)
        return Decoded(name, "%s %s, %s" % (name, R[lo3], R[mid3]),
                       "%s 和 %s %s，结果放回 %s" % (R[lo3], R[mid3], what, R[lo3]),
                       rd=lo3, rm=mid3)
    if hw >> 7 == 0b010001110:
        rm = hw >> 3 & 0xF
        return Decoded("BX", "BX %s" % R[rm], "跳到 %s 里存的地址（函数返回）" % R[rm], rm=rm)
    if hw >> 11 == 0b01001:
        rd, imm = hw >> 8 & 7, (hw & 0xFF) * 4
        addr = ((pc + 4) & ~3) + imm
        return Decoded("LDR_LIT", "LDR %s, [PC, #%d]" % (R[rd], imm),
                       "从地址 %s 读一个常数放进 %s" % (hex32(addr), R[rd]), rd=rd, imm=imm)
    if hw >> 12 in (0b0110, 0b0111):
        byte = hw >> 12 & 1
        load = hw >> 11 & 1
        imm = (hw >> 6 & 0x1F) * (1 if byte else 4)
        name = ("LDR" if load else "STR") + ("B" if byte else "")
        unit = "1 个字节" if byte else "一个字（4 字节）"
        desc = ("从地址 %s+%d 读%s放进 %s" % (R[mid3], imm, unit, R[lo3]) if load else
                "把 %s 写到地址 %s+%d（%s）" % (R[lo3], R[mid3], imm, unit))
        return Decoded(name, "%s %s, [%s, #%d]" % (name, R[lo3], R[mid3], imm), desc,
                       rd=lo3, rn=mid3, imm=imm)
    if hw >> 12 == 0b1001:
        load = hw >> 11 & 1
        rd, imm = hw >> 8 & 7, (hw & 0xFF) * 4
        name = "LDR" if load else "STR"
        desc = ("从栈上 SP+%d 读一个字放进 %s" % (imm, R[rd]) if load else
                "把 %s 存到栈上 SP+%d" % (R[rd], imm))
        return Decoded(name + "_SP", "%s %s, [SP, #%d]" % (name, R[rd], imm), desc,
                       rd=rd, imm=imm)
    if hw >> 8 == 0b10110000:
        imm = (hw & 0x7F) * 4
        if hw & 0x80:
            return Decoded("SUB_SP", "SUB SP, SP, #%d" % imm, "栈指针减 %d" % imm, imm=imm)
        return Decoded("ADD_SP", "ADD SP, SP, #%d" % imm, "栈指针加 %d" % imm, imm=imm)
    if hw >> 9 in (0b1011010, 0b1011110):
        pop = hw >> 11 & 1
        regs = [i for i in range(8) if hw >> i & 1]
        if hw >> 8 & 1:
            regs.append(PC if pop else LR)
        if pop:
            return Decoded("POP", "POP %s" % _rl(regs), "从栈里依次取回 %s" % _rl(regs),
                           regs=regs)
        return Decoded("PUSH", "PUSH %s" % _rl(regs), "把 %s 压进栈保存起来" % _rl(regs),
                       regs=regs)
    if hw >> 12 == 0b1101 and (hw >> 8 & 0xF) < 14:
        cond = hw >> 8 & 0xF
        off = _sext(hw & 0xFF, 8) * 2
        target = (pc + 4 + off) & MASK
        return Decoded("BCOND", "B%s %s" % (COND_NAMES[cond], hex32(target)),
                       "如果%s就跳到 %s" % (COND_TEXT[cond], hex32(target)), imm=off, cond=cond)
    if hw >> 11 == 0b11100:
        off = _sext(hw & 0x7FF, 11) * 2
        target = (pc + 4 + off) & MASK
        return Decoded("B", "B %s" % hex32(target), "无条件跳到 %s" % hex32(target), imm=off)
    if hw >> 11 == 0b11110 and hw2 is not None and hw2 >> 14 == 0b11 and hw2 >> 12 & 1:
        s = hw >> 10 & 1
        j1 = hw2 >> 13 & 1
        j2 = hw2 >> 11 & 1
        i1 = 1 - (j1 ^ s)
        i2 = 1 - (j2 ^ s)
        off = (s << 24 | i1 << 23 | i2 << 22 | (hw & 0x3FF) << 12 | (hw2 & 0x7FF) << 1)
        off = _sext(off, 25)
        target = (pc + 4 + off) & MASK
        return Decoded("BL", "BL %s" % hex32(target),
                       "调用函数：记下返回地址，跳到 %s" % hex32(target), imm=off)
    return Decoded("UNDEF", "??? %04X" % hw, "不认识的机器码")


def _sext(v, bits):
    return v - (1 << bits) if v >> (bits - 1) & 1 else v


class Machine:
    """一颗完整的模拟芯片：总线 + CPU + 已烧录的程序。"""

    def __init__(self, program):
        self.program = program
        self.bus = Bus()
        self.cpu = CPU(self.bus)
        self.reset()

    def reset(self):
        """相当于重新烧录程序后按下复位键。"""
        self.bus.flash[:] = bytes(len(self.bus.flash))
        self.bus.sram[:] = bytes(len(self.bus.sram))
        for addr, value, size in self.program.image():
            mem, off = self.bus._locate(addr, size)
            mem[off:off + size] = value.to_bytes(size, "little")
        self.cpu.reset()

    def step(self):
        return self.cpu.step()
