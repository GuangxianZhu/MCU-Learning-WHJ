"""模拟器里的例程。每个例程同时写好 C 代码和它编译后的汇编（逐行对应）。

汇编会被 asm.py 真正翻译成机器码烧进模拟 Flash，CPU 执行的是机器码。
C 代码不会被编译，它只是给人看的“这几条汇编是哪行 C 变来的”。

内存布局（和真实 STM32 程序一样）：
    0x0800 0000  向量表第 0 个字：栈顶地址（复位时装进 SP）
    0x0800 0004  向量表第 1 个字：复位后第一条指令的地址
    0x0800 0008  程序代码，后面跟着“文字池”（LDR Rx, =... 用到的常数）
    0x2000 0000  全局变量，一个变量占 4 字节
    0x2000 5000  栈顶，栈往低地址长
"""

from . import asm
from .machine import FLASH_BASE, SRAM_BASE, STACK_TOP

CODE_BASE = FLASH_BASE + 8


class Program:
    def __init__(self, key, title, summary, c_lines, source, variables=(), note=""):
        self.key = key
        self.title = title
        self.summary = summary
        self.c_lines = c_lines
        self.source = source            # [(C 行号, 汇编文本), ...]
        self.variables = list(variables)  # [(名字, 初值), ...]
        self.note = note
        self.symbols = {name: SRAM_BASE + 4 * i for i, (name, _) in enumerate(self.variables)}
        self.lines, self.literals, self.end = asm.assemble(source, CODE_BASE, self.symbols)

    def image(self):
        """烧录内容：[(地址, 值, 字节数), ...]。变量初值也放好（真实芯片由启动代码复制过去）。"""
        out = [(FLASH_BASE, STACK_TOP, 4), (FLASH_BASE + 4, CODE_BASE | 1, 4)]
        for ln in self.lines:
            for k, hw in enumerate(ln.code):
                out.append((ln.addr + 2 * k, hw, 2))
        for addr, value, _ in self.literals:
            out.append((addr, value, 4))
        for name, init in self.variables:
            out.append((self.symbols[name], init & 0xFFFFFFFF, 4))
        return out

    def names(self):
        """地址 -> 说明，内存表里用。"""
        out = {FLASH_BASE: "向量表：栈顶地址", FLASH_BASE + 4: "向量表：复位地址"}
        for name, addr in self.symbols.items():
            out[addr] = "变量 %s" % name
        for addr, _, what in self.literals:
            out[addr] = "文字池：" + what
        for ln in self.lines:
            if ln.code:
                out.setdefault(ln.addr & ~3, "程序代码")
        return out

    def line_at(self, addr):
        for i, ln in enumerate(self.lines):
            if ln.code and ln.addr == addr:
                return i
        return None


PROGRAMS = {}


def _add(p):
    PROGRAMS[p.key] = p
    return p


_add(Program(
    "vars", "变量住在哪", "三个变量在 SRAM 里的地址，c = a + b",
    ["int a = 5;          // 全局变量都放在 SRAM",
     "int b = 7;",
     "int c;              // 没写初值，就是 0",
     "",
     "int main(void) {",
     "    c = a + b;",
     "    while (1) { }   // MCU 的程序永远不结束",
     "}"],
    [(4, "main:"),
     (5, "LDR  R3, =a         ; R3 = 变量 a 的地址"),
     (5, "LDR  R0, [R3, #0]   ; R0 = a"),
     (5, "LDR  R1, [R3, #4]   ; R1 = b（a 后面 4 字节）"),
     (5, "ADDS R2, R0, R1     ; R2 = a + b"),
     (5, "STR  R2, [R3, #8]   ; c = R2"),
     (6, "hang: B hang"),
     ],
    [("a", 5), ("b", 7), ("c", 0)],
    "程序（机器码）在 Flash，变量在 SRAM，地址一个挨一个，每个占 4 字节。"))

_add(Program(
    "copy", "一次读、一次写", "b = a; a = 0; 看总线上的读和写",
    ["int a = 0x12345678;",
     "int b;",
     "",
     "int main(void) {",
     "    b = a;        // 一次读 + 一次写",
     "    a = 0;        // 一次写",
     "    while (1) { }",
     "}"],
    [(3, "main:"),
     (4, "LDR  R2, =a"),
     (4, "LDR  R0, [R2, #0]   ; 读 a"),
     (4, "STR  R0, [R2, #4]   ; 写 b"),
     (5, "MOVS R1, #0"),
     (5, "STR  R1, [R2, #0]   ; 写 a"),
     (6, "hang: B hang"),
     ],
    [("a", 0x12345678), ("b", 0)],
    "注意第一条 LDR R2, =a：它从 Flash 的文字池里读数，也是一次总线读。"))

_add(Program(
    "inc", "a = a + 1", "一行 C 变成三条指令：读、加、写",
    ["int a = 5;",
     "",
     "int main(void) {",
     "    while (1) {",
     "        a = a + 1;",
     "    }",
     "}"],
    [(2, "main:"),
     (4, "LDR  R1, =a         ; 编译器把“取 a 的地址”提到循环外面"),
     (4, "loop: LDR  R0, [R1, #0]   ; 读：R0 = a"),
     (4, "ADDS R0, R0, #1     ; 算：R0 = R0 + 1"),
     (4, "STR  R0, [R1, #0]   ; 写：a = R0"),
     (3, "B    loop"),
     ],
    [("a", 5)],
    "CPU 不能直接把 SRAM 里的数加 1：必须先读进寄存器，在 ALU 里算，再写回去。"))

_add(Program(
    "flags", "标志位与溢出", "0-1 等于几？最大的数再加 1 会怎样？",
    ["unsigned int x = 0;",
     "x = x - 1;     // 变成 0xFFFFFFFF，也就是 -1",
     "x = x + 1;     // 又回到 0：进位 C=1，零 Z=1",
     "int y = 0x7FFFFFFF;  // 最大的正数",
     "y = y + 1;     // 变成负数！溢出 V=1",
     "while (1) { }"],
    [(0, "MOVS R0, #0"),
     (1, "SUBS R0, R0, #1"),
     (2, "ADDS R0, R0, #1"),
     (3, "LDR  R1, =0x7FFFFFFF"),
     (4, "ADDS R1, R1, #1"),
     (5, "hang: B hang"),
     ],
    [],
    "变量都放在寄存器里，专门看 ALU 和 NZCV 四个标志位。"))

_add(Program(
    "alarm", "if 怎么实现", "温度超过 30 就报警：CMP + 条件跳转",
    ["int t = 24;         // 温度",
     "int alarm = 0;      // 1 = 报警",
     "",
     "int main(void) {",
     "    while (1) {",
     "        t = t + 3;  // 假装温度在上升",
     "        if (t > 30) {",
     "            alarm = 1;",
     "        } else {",
     "            alarm = 0;",
     "        }",
     "    }",
     "}"],
    [(3, "main:"),
     (4, "LDR  R3, =t"),
     (5, "loop: LDR  R0, [R3, #0]"),
     (5, "ADDS R0, R0, #3"),
     (5, "STR  R0, [R3, #0]"),
     (6, "CMP  R0, #30        ; 算 t - 30，设置标志位"),
     (6, "BLE  no_alarm       ; t <= 30 就跳过报警"),
     (7, "MOVS R1, #1"),
     (7, "B    save"),
     (9, "no_alarm: MOVS R1, #0"),
     (7, "save: STR  R1, [R3, #4]"),
     (4, "B    loop"),
     ],
    [("t", 24), ("alarm", 0)],
    "if 在 CPU 里就是“先比较（CMP），再看标志位决定跳不跳（BLE）”。"))

_add(Program(
    "calls", "函数调用与栈", "main 调 sum3，sum3 再调两次 add",
    ["int s;",
     "",
     "int add(int x, int y) {",
     "    return x + y;",
     "}",
     "",
     "int sum3(int x, int y, int z) {",
     "    int t = add(x, y);",
     "    return add(t, z);",
     "}",
     "",
     "int main(void) {",
     "    s = sum3(1, 2, 3);",
     "    while (1) { }",
     "}"],
    [(11, "main:"),
     (12, "MOVS R0, #1         ; 参数放在 R0、R1、R2"),
     (12, "MOVS R1, #2"),
     (12, "MOVS R2, #3"),
     (12, "BL   sum3           ; 调用：返回地址存进 LR"),
     (12, "LDR  R3, =s"),
     (12, "STR  R0, [R3, #0]   ; 返回值在 R0"),
     (13, "hang: B hang"),
     (6, "sum3: PUSH {R4, LR}   ; 它还要调别人，先把 LR 存进栈"),
     (6, "MOVS R4, R2         ; z 暂存进 R4（R4 用前要先保存）"),
     (7, "BL   add"),
     (8, "MOVS R1, R4"),
     (8, "BL   add"),
     (9, "POP  {R4, PC}       ; 取回 R4，返回地址直接弹进 PC"),
     (2, "add: ADDS R0, R0, R1"),
     (3, "BX   LR             ; 不调别人的函数直接用 LR 返回"),
     ],
    [("s", 0)],
    "BL 把返回地址放进 LR；函数里要再调别人，就得先把 LR 压进栈，不然会被覆盖。"))

_add(Program(
    "bits", "位操作", "|= 置 1、&= ~ 清 0、^= 翻转",
    ["unsigned int reg = 0x0F;",
     "",
     "int main(void) {",
     "    reg |= (1 << 7);    // 第 7 位置 1",
     "    reg &= ~(1 << 2);   // 第 2 位清 0",
     "    reg ^= (1 << 0);    // 第 0 位翻转",
     "    while (1) { }",
     "}"],
    [(2, "main:"),
     (3, "LDR  R3, =reg"),
     (3, "LDR  R0, [R3, #0]"),
     (3, "MOVS R1, #1"),
     (3, "LSLS R1, R1, #7"),
     (3, "ORRS R0, R1"),
     (4, "MOVS R1, #1"),
     (4, "LSLS R1, R1, #2"),
     (4, "BICS R0, R1"),
     (5, "MOVS R1, #1"),
     (5, "EORS R0, R1"),
     (5, "STR  R0, [R3, #0]"),
     (6, "hang: B hang"),
     ],
    [("reg", 0x0F)],
    "把 1 左移 n 位做出“只有第 n 位是 1”的数，再和变量做或 / 清除 / 异或。"))

ORDER = ["inc", "vars", "copy", "alarm", "flags", "calls", "bits"]
