"""模拟器内核的单元测试：机器码编码要和真实 ARM Thumb 一致，例程要算出正确结果。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcu3d.sim import asm  # noqa: E402
from mcu3d.sim.machine import STACK_TOP, Machine, add_with_carry, decode  # noqa: E402
from mcu3d.sim.programs import PROGRAMS  # noqa: E402

# (汇编, 期望的机器码)：数值来自 ARMv7-M 架构手册的编码表
KNOWN = [
    ("MOVS R0, #1", [0x2001]),
    ("MOVS R4, R2", [0x0014]),
    ("ADDS R0, R0, #1", [0x1C40]),
    ("ADDS R2, R0, R1", [0x1842]),
    ("ADDS R0, #200", [0x30C8]),
    ("SUBS R0, R0, #1", [0x1E40]),
    ("CMP R0, #30", [0x281E]),
    ("CMP R0, R1", [0x4288]),
    ("ANDS R0, R1", [0x4008]),
    ("ORRS R0, R1", [0x4308]),
    ("EORS R0, R1", [0x4048]),
    ("BICS R0, R1", [0x4388]),
    ("MVNS R0, R1", [0x43C8]),
    ("MULS R0, R1", [0x4348]),
    ("LSLS R1, R1, #7", [0x01C9]),
    ("LSRS R1, R2, #3", [0x08D1]),
    ("LDR R0, [R1, #0]", [0x6808]),
    ("STR R2, [R3, #8]", [0x609A]),
    ("LDRB R0, [R1, #3]", [0x78C8]),
    ("STRB R0, [R1, #3]", [0x70C8]),
    ("LDR R0, [SP, #4]", [0x9801]),
    ("STR R1, [SP, #8]", [0x9102]),
    ("ADD SP, SP, #16", [0xB004]),
    ("SUB SP, SP, #8", [0xB082]),
    ("PUSH {R4, LR}", [0xB510]),
    ("POP {R4, PC}", [0xBD10]),
    ("BX LR", [0x4770]),
    ("NOP", [0xBF00]),
]


def _one(text, origin=0x08000008):
    lines, _, _ = asm.assemble([(None, text)], origin)
    return lines[-1].code


def test_encodings():
    for text, code in KNOWN:
        assert _one(text) == code, (text, [hex(c) for c in _one(text)], [hex(c) for c in code])


def test_branches():
    src = [(None, "here: B here"), (None, "BEQ here"), (None, "BL far"), (None, "NOP"),
           (None, "far: BX LR")]
    lines, _, _ = asm.assemble(src, 0x08000008)
    code = [ln.code for ln in lines if ln.code]
    assert code[0] == [0xE7FE]               # 跳到自己
    assert code[1] == [0xD0FD]               # 往回跳 1 条
    assert code[2] == [0xF000, 0xF801]       # BL 向前 2 字节


def test_decode_roundtrip():
    """译码器认出的指令，再汇编一遍应该得到同样的机器码。"""
    for text, code in KNOWN:
        d = decode(code[0], None, 0x08000008)
        assert _one(d.text) == code, (text, d.text)


def test_add_with_carry():
    assert add_with_carry(0xFFFFFFFF, 1, 0)[0] == 0
    assert add_with_carry(0xFFFFFFFF, 1, 0)[2] == 1          # C
    assert add_with_carry(0x7FFFFFFF, 1, 0)[3] == 1          # V
    res, carries, c, v = add_with_carry(5, 3, 0)
    assert res == 8 and carries == 0b1110 and c == 0 and v == 0


def run(key, n=60):
    m = Machine(PROGRAMS[key])
    for _ in range(n):
        beats = m.step()
        assert beats[-1].kind != "fault", beats[-1].text
    return m


def var(m, key, name):
    return m.bus.peek(PROGRAMS[key].symbols[name])


def test_programs():
    assert var(run("vars"), "vars", "c") == 12
    m = run("copy")
    assert var(m, "copy", "b") == 0x12345678 and var(m, "copy", "a") == 0
    m = run("inc", 1 + 1 + 4 * 10)          # 复位 + 取地址 + 10 圈
    assert var(m, "inc", "a") == 15
    m = run("flags", 6)
    assert m.cpu.r[0] == 0 and m.cpu.r[1] == 0x80000000
    assert m.cpu.flags == {"N": 1, "Z": 0, "C": 0, "V": 1}
    m = run("alarm", 2 + 9 * 3)
    assert var(m, "alarm", "t") == 33 and var(m, "alarm", "alarm") == 1
    m = run("calls", 30)
    assert var(m, "calls", "s") == 6 and m.cpu.r[13] == STACK_TOP
    assert var(run("bits"), "bits", "reg") == 0x8A


def test_reset_sequence():
    m = Machine(PROGRAMS["inc"])
    beats = m.step()
    assert [b.kind for b in beats] == ["mem_read", "write_reg", "mem_read", "write_reg"]
    assert m.cpu.r[13] == STACK_TOP and m.cpu.r[15] == 0x08000008


def test_fault_on_bad_address():
    src = [(None, "LDR R1, =0x30000000"), (None, "LDR R0, [R1, #0]")]
    from mcu3d.sim.programs import Program
    m = Machine(Program("bad", "bad", "", ["x"], src))
    m.step()
    m.step()
    assert m.step()[-1].kind == "fault"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("模拟器内核测试通过")
