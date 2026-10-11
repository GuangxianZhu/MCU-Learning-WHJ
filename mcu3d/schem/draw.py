"""Logisim 风格的 2D 电路图画笔。

所有东西都画在 X（向右）- Z（向上）平面上，相机用正交投影从正前方看，
所以看起来就是一张平面的电路图。1 个世界单位 ≈ Logisim 里的 1 格。

配色按 Logisim 的习惯：
    亮绿 = 这根线是 1（高电平）      深绿 = 这根线是 0（低电平）
    蓝   = 悬空（没有人在驱动这根线）  黑色粗线 = 多位总线，旁边写着它的值
另外为了上课，加了一种：橙色粗线 = 这一拍正在传数据的总线。
"""

import math

from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter, NodePath, TextNode)

from ..ui import get_font

BG = (1.0, 1.0, 1.0, 1)
GRID = (0.78, 0.8, 0.84, 1)
INK = (0.08, 0.08, 0.1, 1)
INK_DIM = (0.42, 0.44, 0.5, 1)
FILL = (1.0, 1.0, 1.0, 1)
FILL_ACTIVE = (1.0, 0.93, 0.62, 1)
BIT1 = (0.0, 0.82, 0.0, 1)
BIT0 = (0.0, 0.38, 0.0, 1)
FLOAT = (0.2, 0.36, 0.95, 1)
BUS = (0.12, 0.12, 0.14, 1)
ACTIVE = (0.95, 0.45, 0.0, 1)
LABEL_BLUE = (0.1, 0.3, 0.75, 1)

WIRE_W = 0.14   # 1 位导线的粗细
BUS_W = 0.32    # 多位总线的粗细

# 前后层次（y 越小越靠近相机）
Y_GRID, Y_FILL, Y_WIRE, Y_LINE, Y_DOT, Y_TEXT = 0.6, 0.4, 0.3, 0.2, 0.15, -0.1


def _mesh(name, tris_xz, y):
    """一组三角形（每个是三个 (x, z) 点）做成一个白色的几何体，颜色之后用 setColor 改。"""
    vdata = GeomVertexData(name, GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")
    prim = GeomTriangles(Geom.UHStatic)
    i = 0
    for tri in tris_xz:
        # 相机在 -Y 方向往 +Y 看，(x 向右, z 向上) 逆时针就是正面；两面都画省得操心
        for x, z in tri:
            vw.addData3(x, y, z)
            cw.addData4(1, 1, 1, 1)
        prim.addVertices(i, i + 1, i + 2)
        prim.addVertices(i, i + 2, i + 1)
        i += 3
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def _seg_tris(a, b, w):
    """线段 a-b 变成宽 w 的长方形（两头各多出 w/2，拐角处就不会有缺口）。"""
    (x0, z0), (x1, z1) = a, b
    dx, dz = x1 - x0, z1 - z0
    n = math.hypot(dx, dz)
    if n < 1e-9:
        return []
    ux, uz = dx / n * w / 2, dz / n * w / 2
    px, pz = -uz, ux
    p = [(x0 - ux + px, z0 - uz + pz), (x1 + ux + px, z1 + uz + pz),
         (x1 + ux - px, z1 + uz - pz), (x0 - ux - px, z0 - uz - pz)]
    return [(p[0], p[1], p[2]), (p[0], p[2], p[3])]


def polyline_tris(points, w):
    out = []
    for a, b in zip(points, points[1:]):
        out += _seg_tris(a, b, w)
    return out


def fan_tris(points):
    """多边形（从它的重心看过去是“星形”的就行）切成三角形。"""
    cx = sum(p[0] for p in points) / len(points)
    cz = sum(p[1] for p in points) / len(points)
    out = []
    for a, b in zip(points, points[1:] + points[:1]):
        out.append(((cx, cz), a, b))
    return out


def arc(cx, cz, r, a0, a1, n=16):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             cz + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def bits_text(value, bits):
    if value is None:
        return "x" * bits if bits <= 4 else "悬空"
    if bits == 1:
        return str(value & 1)
    if bits <= 4:
        return format(value, "0%db" % bits)
    if bits <= 16:
        return "0x%0*X" % ((bits + 3) // 4, value)
    return "0x%04X %04X" % (value >> 16 & 0xFFFF, value & 0xFFFF)


class Wire:
    """一根导线（bits=1）或一条总线（bits>1）。set() 改它的值，颜色跟着变。"""

    def __init__(self, canvas, points, bits=1, probe=None, probe_align="left", prefix="",
                 tag=None):
        self.bits = bits
        self.prefix = prefix
        self.np = _mesh("wire", polyline_tris(points, BUS_W if bits > 1 else WIRE_W), Y_WIRE)
        self.np.reparentTo(canvas.root)
        if tag:
            canvas.pickable(self.np, tag)
        self.probe = None
        if probe is not None:
            self.probe = canvas.text("", probe[0], probe[1], 0.62, LABEL_BLUE, probe_align)
        self.set(None)

    def set(self, value, active=False):
        if self.bits == 1:
            color = FLOAT if value is None else (BIT1 if value & 1 else BIT0)
            if active and value is None:
                color = ACTIVE
        else:
            color = FLOAT if value is None else (ACTIVE if active else BUS)
        self.np.setColor(color)
        if self.probe is not None:
            self.probe.node().setText(self.prefix + bits_text(value, self.bits))
            self.probe.node().setTextColor(ACTIVE if active and value is not None
                                           else (FLOAT if value is None else LABEL_BLUE))


class Shape:
    """有填充和黑色边框的东西：方块、门电路、多路选择器……可以被点选、可以高亮。"""

    def __init__(self, canvas, outline, tag=None, line_w=0.1, fill=FILL):
        self.fill_color = fill
        self.fill = _mesh("fill", fan_tris(outline), Y_FILL)
        self.fill.reparentTo(canvas.root)
        self.fill.setColor(fill)
        self.edge = _mesh("edge", polyline_tris(outline + outline[:1], line_w), Y_LINE)
        self.edge.reparentTo(canvas.root)
        self.edge.setColor(INK)
        if tag:
            canvas.pickable(self.fill, tag)

    def set_active(self, on):
        self.fill.setColor(FILL_ACTIVE if on else self.fill_color)

    def set_fill(self, color):
        self.fill_color = color
        self.fill.setColor(color)


class Canvas:
    """一张电路图。lesson 是课程对象（用它的 make_pickable 让东西能被鼠标点到）。"""

    def __init__(self, lesson, parent=None):
        self.lesson = lesson
        self.root = (parent or lesson.root).attachNewNode("schematic")
        self.root.setLightOff(1)
        self.root.setTwoSided(True)

    def destroy(self):
        self.root.removeNode()

    def pickable(self, np, tag):
        self.lesson.make_pickable(np, tag)

    # ---- 背景 ----
    def paper(self, x0, z0, x1, z1):
        """白纸 + Logisim 那样的灰色网格点。"""
        bg = _mesh("paper", [((x0, z0), (x1, z0), (x1, z1)), ((x0, z0), (x1, z1), (x0, z1))],
                   Y_GRID + 0.1)
        bg.reparentTo(self.root)
        bg.setColor(BG)
        dots = []
        s = 0.06
        for gx in range(int(math.ceil(x0)), int(x1) + 1):
            for gz in range(int(math.ceil(z0)), int(z1) + 1):
                dots.append(((gx - s, gz - s), (gx + s, gz - s), (gx + s, gz + s)))
                dots.append(((gx - s, gz - s), (gx + s, gz + s), (gx - s, gz + s)))
        g = _mesh("grid", dots, Y_GRID)
        g.reparentTo(self.root)
        g.setColor(GRID)

    # ---- 文字 ----
    def text(self, s, x, z, size=0.7, color=INK, align="left"):
        tn = TextNode("t")
        font = get_font()
        if font is not None:
            tn.setFont(font)
        tn.setText(s)
        tn.setTextColor(*color)
        tn.setAlign({"left": TextNode.ALeft, "center": TextNode.ACenter,
                     "right": TextNode.ARight}[align])
        np = self.root.attachNewNode(tn)
        np.setPos(x, Y_TEXT, z)
        np.setScale(size)
        return np

    # ---- 线 ----
    def wire(self, points, bits=1, probe=None, probe_align="left", prefix="", tag=None):
        return Wire(self, points, bits, probe, probe_align, prefix, tag)

    def line(self, points, color=INK, w=0.08):
        np = _mesh("line", polyline_tris(points, w), Y_LINE)
        np.reparentTo(self.root)
        np.setColor(color)
        return np

    def dot(self, x, z, r=0.22):
        """导线连在一起的地方画一个圆点（Logisim 里只有画了点才算接通）。"""
        np = _mesh("dot", fan_tris(arc(x, z, r, 0, 360, 12)[:-1]), Y_DOT)
        np.reparentTo(self.root)
        np.setColor(INK)
        return np

    # ---- 元件 ----
    def box(self, x0, z0, x1, z1, title="", tag=None, title_size=0.75, fill=FILL,
            sub=None):
        shape = Shape(self, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], tag, fill=fill)
        if title:
            self.text(title, (x0 + x1) / 2, z1 - 0.95 * title_size - 0.2, title_size, INK,
                      "center")
        if sub:
            self.text(sub, (x0 + x1) / 2, z0 + 0.35, 0.5, INK_DIM, "center")
        return shape

    def pin_in(self, x, z, label="", tag=None, label_side="left"):
        """Logisim 的输入引脚：方框，里面写着现在的值。返回 (外形, 值文字)。"""
        shape = Shape(self, [(x - 0.9, z - 0.6), (x + 0.3, z - 0.6), (x + 0.3, z + 0.6),
                             (x - 0.9, z + 0.6)], tag)
        val = self.text("0", x - 0.3, z - 0.3, 0.8, INK, "center")
        if label:
            if label_side == "left":
                self.text(label, x - 1.2, z - 0.25, 0.6, INK, "right")
            else:
                self.text(label, x - 0.3, z + 0.9, 0.6, INK, "center")
        return shape, val

    def pin_out(self, x, z, label="", label_side="right"):
        """Logisim 的输出引脚：圆角框。"""
        pts = arc(x + 0.6, z, 0.6, -90, 90, 10) + [(x - 0.3, z + 0.6), (x - 0.3, z - 0.6)]
        shape = Shape(self, pts)
        val = self.text("0", x + 0.25, z - 0.3, 0.8, INK, "center")
        if label:
            if label_side == "right":
                self.text(label, x + 1.5, z - 0.25, 0.6, INK, "left")
            else:
                self.text(label, x + 0.25, z + 0.9, 0.6, INK, "center")
        return shape, val

    def gate(self, kind, x, z, tag=None, facing="right", size=1.0):
        """门电路。(x, z) 是门的输入侧中点。返回 Gate，带 a / b / out 三个引脚坐标。"""
        return Gate(self, kind, x, z, tag, facing, size)

    def mux(self, x, z, n_in, h_step=1.6, tag=None, label="MUX"):
        """多路选择器（梯形）。(x, z) 是左边中点。返回 (外形, 输入坐标列表, 输出坐标, 选择端坐标)。"""
        h = n_in * h_step / 2 + 0.5
        pts = [(x, z - h), (x + 1.6, z - h + 0.8), (x + 1.6, z + h - 0.8), (x, z + h)]
        shape = Shape(self, pts, tag)
        ins = [(x, z + h - 0.5 - h_step / 2 - k * h_step) for k in range(n_in)]
        self.text(label, x + 0.8, z - 0.2, 0.42, INK_DIM, "center")
        return shape, ins, (x + 1.6, z), (x + 0.8, z - h + 0.4)


class Gate:
    """与门 AND、或门 OR、异或门 XOR、与非门 NAND、非门 NOT。"""

    def __init__(self, canvas, kind, x, z, tag, facing, size):
        s = size
        body, bubble = self._outline(kind, s)
        self.kind = kind
        rot = {"right": (1, 0, 0, 1), "down": (0, 1, -1, 0)}[facing]

        def tr(p):
            px, pz = p
            return (x + rot[0] * px + rot[1] * pz, z + rot[2] * px + rot[3] * pz)

        self.shape = Shape(canvas, [tr(p) for p in body], tag)
        if kind in ("OR", "XOR", "NOR"):
            # 输入线伸进凹进去的背面
            for zz in (0.5 * s, -0.5 * s):
                canvas.line([tr((0, zz)), tr((0.42 * s, zz))], INK, 0.08)
        if kind == "XOR":
            canvas.line([tr(p) for p in arc(-0.9 * s, 0, 1.2 * s, -50, 50, 10)], INK, 0.1)
        out_x = 2.0 * s if kind != "NOT" else 1.3 * s
        if bubble:
            Shape(canvas, [tr(p) for p in arc(out_x + 0.18 * s, 0, 0.18 * s, 0, 360, 10)[:-1]])
            out_x += 0.36 * s
        if kind == "NOT":
            self.a = self.b = tr((0, 0))
        else:
            self.a = tr((0, 0.5 * s))
            self.b = tr((0, -0.5 * s))
        self.out = tr((out_x, 0))

    @staticmethod
    def _outline(kind, s):
        if kind in ("AND", "NAND"):
            pts = [(0, -1 * s), (1 * s, -1 * s)] + arc(1 * s, 0, 1 * s, -90, 90)[1:-1] + \
                  [(1 * s, 1 * s), (0, 1 * s)]
            return pts, kind == "NAND"
        if kind in ("OR", "XOR", "NOR"):
            # 背面是向里凹的弧，正面两条弧在右边尖端汇合
            back = arc(-0.7 * s, 0, 1.2 * s, 56, -56, 10)
            front_lo = [(0.3 * s + 1.9 * s * t - 0.2 * s * t * t, -1 * s + 1 * s * t * t)
                        for t in [k / 10 for k in range(11)]]
            front_hi = [(px, -pz) for px, pz in reversed(front_lo)]
            pts = [(back[0][0], 1 * s)] + back[1:-1] + [(back[-1][0], -1 * s)] + \
                front_lo[1:] + front_hi[1:-1]
            return pts, kind == "NOR"
        if kind == "NOT":
            return [(0, -0.7 * s), (1.3 * s, 0), (0, 0.7 * s)], True
        raise ValueError(kind)
