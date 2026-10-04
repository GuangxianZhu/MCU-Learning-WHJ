"""程序化生成的几何体（不依赖任何模型文件）。

坐标约定：Panda3D 是 Z 轴朝上，X 向右，Y 向屏幕里。
"""

import math

from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter, LineSegs,
                          NodePath, TransparencyAttrib)

# 每个面：法线 n 与两条切向量 u、v（u × v = n，保证逆时针为正面）
_FACES = [
    ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
    ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
]


def _writer(name):
    vdata = GeomVertexData(name, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
    return (vdata, GeomVertexWriter(vdata, "vertex"),
            GeomVertexWriter(vdata, "normal"), GeomVertexWriter(vdata, "color"))


def _finish(name, vdata, tris):
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def box(size=(1, 1, 1), color=(1, 1, 1, 1), name="box"):
    """以原点为中心的长方体，size 为 (长x, 宽y, 高z)。"""
    h = (size[0] / 2, size[1] / 2, size[2] / 2)
    vdata, vw, nw, cw = _writer(name)
    tris = GeomTriangles(Geom.UHStatic)
    i = 0
    for n, u, v in _FACES:
        c = [n[k] * h[k] for k in range(3)]
        uu = [u[k] * h[k] for k in range(3)]
        vv = [v[k] * h[k] for k in range(3)]
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            vw.addData3(c[0] + su * uu[0] + sv * vv[0],
                        c[1] + su * uu[1] + sv * vv[1],
                        c[2] + su * uu[2] + sv * vv[2])
            nw.addData3(*n)
            cw.addData4(*color)
        tris.addVertices(i, i + 1, i + 2)
        tris.addVertices(i, i + 2, i + 3)
        i += 4
    return _finish(name, vdata, tris)


def cylinder(radius=0.5, height=1.0, color=(1, 1, 1, 1), segments=24,
             name="cylinder"):
    """竖直圆柱，底面中心在原点。"""
    vdata, vw, nw, cw = _writer(name)
    tris = GeomTriangles(Geom.UHStatic)
    idx = 0
    for k in range(segments):
        a0 = 2 * math.pi * k / segments
        a1 = 2 * math.pi * (k + 1) / segments
        p0 = (math.cos(a0), math.sin(a0))
        p1 = (math.cos(a1), math.sin(a1))
        # 侧面
        for (p, z) in ((p0, 0), (p1, 0), (p1, height), (p0, height)):
            vw.addData3(p[0] * radius, p[1] * radius, z)
            nw.addData3(p[0], p[1], 0)
            cw.addData4(*color)
        tris.addVertices(idx, idx + 1, idx + 2)
        tris.addVertices(idx, idx + 2, idx + 3)
        idx += 4
        # 顶面
        for p in ((0, 0), p0, p1):
            vw.addData3(p[0] * radius, p[1] * radius, height)
            nw.addData3(0, 0, 1)
            cw.addData4(*color)
        tris.addVertices(idx, idx + 1, idx + 2)
        idx += 3
        # 底面
        for p in ((0, 0), p1, p0):
            vw.addData3(p[0] * radius, p[1] * radius, 0)
            nw.addData3(0, 0, -1)
            cw.addData4(*color)
        tris.addVertices(idx, idx + 1, idx + 2)
        idx += 3
    return _finish(name, vdata, tris)


def lines(points, color=(1, 1, 1, 1), thickness=2.0, name="lines"):
    """把一串点连成折线。"""
    ls = LineSegs(name)
    ls.setThickness(thickness)
    ls.setColor(*color)
    ls.moveTo(*points[0])
    for p in points[1:]:
        ls.drawTo(*p)
    return NodePath(ls.create())


def flat_trace(p0, p1, width=0.18, height=0.04, color=(1, 1, 1, 1)):
    """两点之间的扁平导线（PCB 走线），只支持水平或竖直方向的线段。"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    np = box((length + width, width, height), color, name="trace")
    np.setPos((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, p0[2])
    np.setH(math.degrees(math.atan2(dy, dx)))
    return np


def make_transparent(np, alpha):
    np.setTransparency(TransparencyAttrib.MAlpha)
    np.setAlphaScale(alpha)
