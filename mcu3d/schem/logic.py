"""三值逻辑：0、1、None（悬空 / 不确定，电路图上画成蓝色）。

Logisim 也是这样：一个门只要有输入悬空，输出就可能不确定；
但与门只要有一个输入是 0，输出就一定是 0，不管另一个是什么。
"""


def NOT(a):
    return None if a is None else 1 - a


def AND(a, b):
    if a == 0 or b == 0:
        return 0
    if a == 1 and b == 1:
        return 1
    return None


def OR(a, b):
    if a == 1 or b == 1:
        return 1
    if a == 0 and b == 0:
        return 0
    return None


def XOR(a, b):
    if a is None or b is None:
        return None
    return a ^ b


def NAND(a, b):
    return NOT(AND(a, b))


def bit(value, k):
    return None if value is None else value >> k & 1


def full_adder(a, b, cin):
    """一位全加器的五个门，返回每个门的输出 (p, s, g, t, cout)。"""
    p = XOR(a, b)
    s = XOR(p, cin)
    g = AND(a, b)
    t = AND(p, cin)
    return p, s, g, t, OR(g, t)


def latch(d, en, q_hold):
    """门控 D 锁存器（4 个与非门 + 输入端一个非门）。

    en=1 时 Q 跟着 D 走（“透明”），en=0 时 Q 保持 q_hold。
    返回 (nd, s, r, q, nq)：非门输出、两个输入与非门的输出、两个交叉耦合与非门的输出。
    """
    nd = NOT(d)
    s = NAND(d, en)
    r = NAND(nd, en)
    if en == 1:
        q = d
    elif en == 0:
        q = q_hold
    else:
        q = None
    nq = NOT(q)
    # 交叉耦合的两个门：Q = NAND(s, nQ)，nQ = NAND(r, Q)，和上面算出的一致
    return nd, s, r, q, nq
