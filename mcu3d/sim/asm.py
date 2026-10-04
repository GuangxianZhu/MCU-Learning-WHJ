"""迷你汇编器：把课程里用到的 Thumb 指令翻译成真实的 16 位机器码。

只支持约 20 条指令（见 MNEMONICS），编码和真实的 ARM Cortex-M 完全一致，
所以面板上的机器码就是芯片里真的会存的数字。

源程序写法（和 Keil / GCC 汇编差不多）：
    loop:                     标号
        LDR  R1, =a           把变量 a 的地址装进 R1（地址放在程序后面的“文字池”里）
        LDR  R0, [R1, #0]
        ADDS R0, R0, #1
        B    loop
"""

import re

REGS = {"R%d" % i: i for i in range(13)}
REGS.update({"SP": 13, "LR": 14, "PC": 15, "R13": 13, "R14": 14, "R15": 15})
REG_NAMES = ["R%d" % i for i in range(13)] + ["SP", "LR", "PC"]

CONDS = {"EQ": 0, "NE": 1, "CS": 2, "HS": 2, "CC": 3, "LO": 3, "MI": 4, "PL": 5,
         "VS": 6, "VC": 7, "HI": 8, "LS": 9, "GE": 10, "LT": 11, "GT": 12, "LE": 13}
COND_NAMES = ["EQ", "NE", "CS", "CC", "MI", "PL", "VS", "VC", "HI", "LS", "GE", "LT",
              "GT", "LE"]

MNEMONICS = ["MOVS", "ADDS", "SUBS", "CMP", "MULS", "ANDS", "ORRS", "EORS", "BICS",
             "MVNS", "LSLS", "LSRS", "LDR", "STR", "LDRB", "STRB", "PUSH", "POP",
             "ADD", "SUB", "B", "BL", "BX", "NOP"] + ["B" + c for c in CONDS]


class AsmError(Exception):
    pass


class Line:
    """汇编后的一行：label 行或指令行。"""

    def __init__(self, text, c_line=None):
        self.text = text            # 原文（去掉注释）
        self.c_line = c_line        # 对应第几行 C 代码（从 0 开始）
        self.label = None
        self.mnemonic = None
        self.ops = []
        self.addr = None
        self.size = 0
        self.code = []              # 16 位半字列表


def _reg(tok, low=True):
    tok = tok.strip().upper()
    if tok not in REGS:
        raise AsmError("不认识的寄存器：%s" % tok)
    r = REGS[tok]
    if low and r > 7:
        raise AsmError("这条指令只能用 R0~R7：%s" % tok)
    return r


def _imm(tok, symbols=None):
    tok = tok.strip()
    if tok.startswith("#"):
        tok = tok[1:]
    try:
        return int(tok, 0)
    except ValueError:
        if symbols and tok in symbols:
            return symbols[tok]
        raise AsmError("不认识的数字：%s" % tok)


def _split_ops(s):
    """按逗号拆操作数，但 [] 和 {} 里的逗号不拆。"""
    ops, depth, cur = [], 0, ""
    for ch in s:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            ops.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        ops.append(cur.strip())
    return ops


def _mem(op):
    """'[R1, #4]' -> ('R1', 4)。"""
    m = re.fullmatch(r"\[\s*(\w+)\s*(?:,\s*#?([-\w]+))?\s*\]", op)
    if not m:
        raise AsmError("内存操作数写法不对：%s" % op)
    return m.group(1).upper(), int(m.group(2) or "0", 0)


def _reglist(op):
    m = re.fullmatch(r"\{(.*)\}", op.strip())
    if not m:
        raise AsmError("寄存器列表要写在 {} 里：%s" % op)
    return [REGS[r.strip().upper()] for r in m.group(1).split(",")]


def _check(v, lo, hi, what):
    if not lo <= v <= hi:
        raise AsmError("%s 超出范围（%d~%d）：%d" % (what, lo, hi, v))
    return v


def _size(mn, ops):
    return 4 if mn == "BL" else 2


def assemble(source, origin, symbols=None):
    """source: [(c_line 或 None, 文本), ...]。返回 (lines, literals, end_addr)。

    literals: [(地址, 值, 说明)]，放在代码后面（4 字节对齐）的“文字池”。
    symbols: 变量名 -> 地址，用于 LDR Rx, =变量名。
    """
    symbols = dict(symbols or {})
    lines = []
    for c_line, raw in source:
        text = re.split(r"[;@]", raw, maxsplit=1)[0].rstrip()
        if not text.strip():
            continue
        m = re.match(r"\s*(\w+):\s*(.*)$", text)
        if m:
            lab = Line(m.group(1) + ":", c_line)
            lab.label = m.group(1)
            lines.append(lab)
            text = m.group(2)
            if not text.strip():
                continue
        ln = Line(text.strip(), c_line)
        parts = text.strip().split(None, 1)
        ln.mnemonic = parts[0].upper()
        if ln.mnemonic not in MNEMONICS:
            raise AsmError("不支持的指令：%s" % parts[0])
        ln.ops = _split_ops(parts[1]) if len(parts) > 1 else []
        lines.append(ln)

    # 第一遍：算地址
    labels = {}
    addr = origin
    literal_keys = []
    for ln in lines:
        ln.addr = addr
        if ln.label:
            labels[ln.label] = addr
            continue
        ln.size = _size(ln.mnemonic, ln.ops)
        addr += ln.size
        if ln.mnemonic == "LDR" and len(ln.ops) == 2 and ln.ops[1].startswith("="):
            key = ln.ops[1][1:].strip()
            if key not in literal_keys:
                literal_keys.append(key)
    pool = (addr + 3) & ~3
    literals = []
    lit_addr = {}
    for k, key in enumerate(literal_keys):
        a = pool + 4 * k
        lit_addr[key] = a
        if key in symbols:
            literals.append((a, symbols[key], "变量 %s 的地址" % key))
        else:
            literals.append((a, _imm(key) & 0xFFFFFFFF, "常数 %s" % key))
    end = pool + 4 * len(literal_keys)

    # 第二遍：编码
    for ln in lines:
        if ln.label:
            continue
        try:
            ln.code = _encode(ln, labels, lit_addr, symbols)
        except AsmError as e:
            raise AsmError("%s（这一行：%s）" % (e, ln.text))
        except (IndexError, ValueError):
            raise AsmError("操作数个数或写法不对（这一行：%s）" % ln.text)
    return lines, literals, end


def _branch_off(ln, labels, target, bits):
    if target not in labels:
        raise AsmError("找不到标号：%s" % target)
    off = labels[target] - (ln.addr + 4)
    half = off >> 1
    lim = 1 << (bits - 1)
    _check(half, -lim, lim - 1, "跳转距离")
    return half & ((1 << bits) - 1)


def _encode(ln, labels, lit_addr, symbols):
    mn, ops = ln.mnemonic, ln.ops
    n = len(ops)
    if mn == "NOP":
        return [0xBF00]
    if mn == "MOVS":
        rd = _reg(ops[0])
        if ops[1].startswith("#"):
            return [0x2000 | rd << 8 | _check(_imm(ops[1]), 0, 255, "立即数")]
        return [0x0000 | _reg(ops[1]) << 3 | rd]          # 就是 LSLS Rd, Rm, #0
    if mn in ("ADDS", "SUBS"):
        sub = mn == "SUBS"
        rd = _reg(ops[0])
        if n == 2:
            if ops[1].startswith("#"):
                return [(0x3800 if sub else 0x3000) | rd << 8
                        | _check(_imm(ops[1]), 0, 255, "立即数")]
            ops = [ops[0], ops[0], ops[1]]
        rn = _reg(ops[1])
        if ops[2].startswith("#"):
            return [(0x1E00 if sub else 0x1C00) | _check(_imm(ops[2]), 0, 7, "立即数")
                    << 6 | rn << 3 | rd]
        return [(0x1A00 if sub else 0x1800) | _reg(ops[2]) << 6 | rn << 3 | rd]
    if mn == "CMP":
        rn = _reg(ops[0])
        if ops[1].startswith("#"):
            return [0x2800 | rn << 8 | _check(_imm(ops[1]), 0, 255, "立即数")]
        return [0x4280 | _reg(ops[1]) << 3 | rn]
    alu = {"ANDS": 0x4000, "EORS": 0x4040, "ORRS": 0x4300, "BICS": 0x4380,
           "MVNS": 0x43C0, "MULS": 0x4340}
    if mn in alu:
        rd = _reg(ops[0])
        rm = _reg(ops[-1])
        if mn == "MULS" and n == 3:      # MULS Rd, Rn, Rd
            rm = _reg(ops[1])
        return [alu[mn] | rm << 3 | rd]
    if mn in ("LSLS", "LSRS"):
        rd = _reg(ops[0])
        if n == 2:
            ops = [ops[0], ops[0], ops[1]]
        imm = _imm(ops[2])
        if mn == "LSRS" and imm == 32:
            imm = 0
        _check(imm, 0 if mn == "LSLS" else 0, 31, "移位位数")
        return [(0x0800 if mn == "LSRS" else 0x0000) | imm << 6 | _reg(ops[1]) << 3 | rd]
    if mn in ("LDR", "STR", "LDRB", "STRB"):
        rt = _reg(ops[0])
        if ops[1].startswith("="):
            if mn != "LDR":
                raise AsmError("只有 LDR 能用 =")
            a = lit_addr[ops[1][1:].strip()]
            base = (ln.addr + 4) & ~3
            return [0x4800 | rt << 8 | _check((a - base) // 4, 0, 255, "文字池距离")]
        base_reg, off = _mem(ops[1])
        if base_reg == "SP":
            if mn not in ("LDR", "STR"):
                raise AsmError("SP 只能配 LDR/STR")
            return [(0x9800 if mn == "LDR" else 0x9000) | rt << 8
                    | _check(off // 4, 0, 255, "偏移")]
        rn = _reg(base_reg)
        if mn in ("LDR", "STR"):
            if off % 4:
                raise AsmError("字（4 字节）访问的偏移必须是 4 的倍数")
            return [(0x6800 if mn == "LDR" else 0x6000) | _check(off // 4, 0, 31, "偏移")
                    << 6 | rn << 3 | rt]
        return [(0x7800 if mn == "LDRB" else 0x7000) | _check(off, 0, 31, "偏移") << 6
                | rn << 3 | rt]
    if mn in ("PUSH", "POP"):
        regs = _reglist(ops[0])
        bits = 0
        extra = 0
        for r in regs:
            if r < 8:
                bits |= 1 << r
            elif (mn == "PUSH" and r == 14) or (mn == "POP" and r == 15):
                extra = 1
            else:
                raise AsmError("%s 只能带 R0~R7 和 %s" % (mn, "LR" if mn == "PUSH" else "PC"))
        return [(0xB400 if mn == "PUSH" else 0xBC00) | extra << 8 | bits]
    if mn in ("ADD", "SUB"):
        if ops[0].upper() != "SP" or (n == 3 and ops[1].upper() != "SP"):
            raise AsmError("ADD/SUB（不带 S）这里只支持 SP")
        imm = _imm(ops[-1])
        if imm % 4:
            raise AsmError("SP 只能加减 4 的倍数")
        return [(0xB080 if mn == "SUB" else 0xB000) | _check(imm // 4, 0, 127, "立即数")]
    if mn == "B":
        return [0xE000 | _branch_off(ln, labels, ops[0], 11)]
    if mn.startswith("B") and mn[1:] in CONDS:
        return [0xD000 | CONDS[mn[1:]] << 8 | _branch_off(ln, labels, ops[0], 8)]
    if mn == "BL":
        if ops[0] not in labels:
            raise AsmError("找不到标号：%s" % ops[0])
        off = labels[ops[0]] - (ln.addr + 4)
        imm = (off >> 1) & 0x3FFFFF
        s = (off >> 24) & 1
        i1 = (off >> 23) & 1
        i2 = (off >> 22) & 1
        j1 = (1 - i1) ^ s
        j2 = (1 - i2) ^ s
        return [0xF000 | s << 10 | (imm >> 11) & 0x3FF,
                0xD000 | j1 << 13 | j2 << 11 | imm & 0x7FF]
    if mn == "BX":
        return [0x4700 | REGS[ops[0].strip().upper()] << 3]
    raise AsmError("不支持的写法")
