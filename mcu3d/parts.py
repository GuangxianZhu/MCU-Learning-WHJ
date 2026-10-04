"""可复用的电子元件：芯片、LED、按键、波形图、沿路径移动的数据包。"""

import math

from panda3d.core import Vec3

from . import shapes, theme
from .ui import flat_text, text3d


class Chip:
    """QFP 封装的芯片：黑色方块 + 四周引脚 + 顶部印字。"""

    def __init__(self, parent, size=4.0, height=0.6, pins_per_side=8,
                 label="MCU", pos=(0, 0, 0)):
        self.np = parent.attachNewNode("chip")
        self.np.setPos(*pos)
        self.size = size
        self.height = height
        self.body = shapes.box((size, size, height), theme.CHIP, "chip-body")
        self.body.reparentTo(self.np)
        self.body.setZ(height / 2 + 0.05)
        self.pins = []
        pitch = size / (pins_per_side + 1)
        pin_len = 0.5
        for side in range(4):
            for k in range(pins_per_side):
                offset = -size / 2 + pitch * (k + 1)
                pin = shapes.box((pin_len, pitch * 0.45, 0.06), theme.PIN, "pin")
                pin.reparentTo(self.np)
                d = size / 2 + pin_len / 2 - 0.05
                pin.setPos([(d, offset), (offset, d), (-d, -offset),
                            (-offset, -d)][side] + (0.12,))
                if side % 2:
                    pin.setH(90)
                self.pins.append(pin)
        self.label = None
        if label:
            self.label = flat_text(label, self.np, (0, 0, height + 0.06),
                                   scale=size * 0.16, color=(0.8, 0.8, 0.8, 1))

    def pin_pos(self, side, k, pins_per_side=8):
        """引脚末端在父节点坐标中的位置。side: 0 右 1 上 2 左 3 下。"""
        pitch = self.size / (pins_per_side + 1)
        offset = -self.size / 2 + pitch * (k + 1)
        d = self.size / 2 + 0.45
        x, y = [(d, offset), (offset, d), (-d, -offset), (-offset, -d)][side]
        p = self.np.getPos()
        return (p[0] + x, p[1] + y, p[2] + 0.12)


class LED:
    """发光二极管。set_level(0~1) 控制亮度。"""

    def __init__(self, parent, pos=(0, 0, 0), color=theme.LED_RED, radius=0.35,
                 label=None):
        self.color = color
        self.np = parent.attachNewNode("led")
        self.np.setPos(*pos)
        base = shapes.box((radius * 2.4, radius * 2.4, 0.2), (0.85, 0.85, 0.85, 1))
        base.reparentTo(self.np)
        base.setZ(0.1)
        self.dome = shapes.cylinder(radius, radius * 1.6, (1, 1, 1, 1), name="dome")
        self.dome.reparentTo(self.np)
        self.dome.setZ(0.2)
        self.halo = shapes.cylinder(radius * 1.7, radius * 2.0, (1, 1, 1, 1))
        self.halo.reparentTo(self.np)
        self.halo.setZ(0.05)
        self.halo.setLightOff(1)
        self.halo.setDepthWrite(False)
        self.halo.setBin("transparent", 10)
        shapes.make_transparent(self.halo, 0)
        if label:
            text3d(label, self.np, (0, 0, radius * 2 + 0.7), scale=0.35,
                   color=theme.TEXT_DIM)
        self.level = None
        self.set_level(0)

    def set_level(self, level):
        level = max(0.0, min(1.0, level))
        if level == self.level:
            return
        self.level = level
        dim = theme.scale(self.color, 0.25)
        self.dome.setColor(*theme.lerp(dim, self.color, level), 1)
        if level > 0.05:
            self.dome.setLightOff(1)
        else:
            self.dome.clearLight()
        self.halo.setColor(*self.color[:3], 1, 1)
        self.halo.setAlphaScale(0.35 * level)

    def set_on(self, on):
        self.set_level(1.0 if on else 0.0)


class Button:
    """轻触按键。"""

    def __init__(self, parent, pos=(0, 0, 0), label=None):
        self.np = parent.attachNewNode("button")
        self.np.setPos(*pos)
        base = shapes.box((1.2, 1.2, 0.35), (0.2, 0.2, 0.22, 1))
        base.reparentTo(self.np)
        base.setZ(0.175)
        self.cap = shapes.cylinder(0.38, 0.3, (0.85, 0.2, 0.2, 1), name="cap")
        self.cap.reparentTo(self.np)
        self.cap.setZ(0.35)
        if label:
            text3d(label, self.np, (0, 0, 1.3), scale=0.35, color=theme.TEXT_DIM)
        self.pressed = False

    def set_pressed(self, pressed):
        self.pressed = pressed
        self.cap.setZ(0.22 if pressed else 0.35)


class Waveform:
    """一条竖直平面里的数字波形（方波）。levels 是 0/1 列表。"""

    def __init__(self, parent, origin=(0, 0, 0), width=8.0, height=1.0,
                 color=theme.ACCENT, thickness=2.5):
        self.parent = parent
        self.origin = origin
        self.width = width
        self.height = height
        self.color = color
        self.thickness = thickness
        self.np = None
        axis = shapes.lines([origin, (origin[0] + width, origin[1], origin[2])],
                            (0.3, 0.3, 0.35, 1), 1.0)
        axis.reparentTo(parent)
        axis.setLightOff(1)

    def set_levels(self, levels):
        if self.np is not None:
            self.np.removeNode()
            self.np = None
        if not levels:
            return
        ox, oy, oz = self.origin
        step = self.width / len(levels)
        pts = []
        for i, lv in enumerate(levels):
            z = oz + (self.height if lv else 0.0)
            pts.append((ox + i * step, oy, z))
            pts.append((ox + (i + 1) * step, oy, z))
        self.np = shapes.lines(pts, self.color, self.thickness)
        self.np.reparentTo(self.parent)
        self.np.setLightOff(1)


class Packet:
    """沿折线路径匀速移动的小方块（代表在总线/导线上传输的数据）。"""

    def __init__(self, parent, path, color=theme.ACCENT, speed=6.0, size=0.45,
                 label=None, on_done=None):
        self.np = shapes.box((size, size, size), color, "packet")
        self.np.reparentTo(parent)
        self.np.setLightOff(1)
        if label:
            text3d(label, self.np, (0, 0, size + 0.4), scale=0.35, color=theme.TEXT)
        self.path = [Vec3(*p) for p in path]
        self.speed = speed
        self.seg = 0
        self.t = 0.0
        self.on_done = on_done
        self.done = False
        self.np.setPos(self.path[0])

    def destroy(self):
        self.done = True
        self.np.removeNode()

    def update(self, dt):
        if self.done:
            return
        remaining = self.speed * dt
        while remaining > 0 and self.seg < len(self.path) - 1:
            a, b = self.path[self.seg], self.path[self.seg + 1]
            seg_len = (b - a).length()
            left = seg_len * (1 - self.t)
            if remaining >= left:
                remaining -= left
                self.seg += 1
                self.t = 0.0
            else:
                self.t += remaining / max(seg_len, 1e-6)
                remaining = 0
        if self.seg >= len(self.path) - 1:
            self.np.setPos(self.path[-1])
            self.done = True
            self.np.removeNode()
            if self.on_done:
                self.on_done()
            return
        a, b = self.path[self.seg], self.path[self.seg + 1]
        self.np.setPos(a + (b - a) * self.t)
        self.np.setH(self.np.getH() + 180 * dt)


class BitTrain:
    """一串比特方块沿直线依次前进（第 0 个打头）。

    bits: 0/1 列表；labels: 每个方块上显示的字（默认显示 0/1）；
    on_bit(i): 第 i 个方块到达终点时调用；on_done(): 全部到达后调用。
    """

    def __init__(self, parent, bits, start, end, bit_time=0.4, spacing=0.8,
                 labels=None, colors=None, size=0.45, on_bit=None, on_done=None):
        self.start = Vec3(*start)
        self.end = Vec3(*end)
        self.length = (self.end - self.start).length()
        self.dir = (self.end - self.start) / max(self.length, 1e-6)
        self.bit_time = bit_time
        self.speed = spacing / bit_time
        self.on_bit = on_bit
        self.on_done = on_done
        self.t = 0.0
        self.arrived = 0
        self.done = False
        self.root = parent.attachNewNode("bit-train")
        self.cubes = []
        for i, b in enumerate(bits):
            color = colors[i] if colors else (theme.HIGH if b else theme.LOW)
            cube = shapes.box((size, size, size), color, "bit")
            cube.reparentTo(self.root)
            cube.setLightOff(1)
            text = labels[i] if labels else str(b)
            text3d(text, cube, (0, 0, size + 0.15), scale=0.32, color=theme.TEXT)
            cube.hide()
            self.cubes.append(cube)

    def current_index(self):
        """发送端此刻正在送出的是第几个比特。"""
        return int(self.t / self.bit_time)

    def destroy(self):
        self.done = True
        self.root.removeNode()

    def update(self, dt):
        if self.done:
            return
        self.t += dt
        for i, cube in enumerate(self.cubes):
            s = (self.t - i * self.bit_time) * self.speed
            if s < 0:
                continue
            if s >= self.length:
                cube.hide()
                if i >= self.arrived:
                    self.arrived = i + 1
                    if self.on_bit:
                        self.on_bit(i)
                continue
            cube.show()
            cube.setPos(self.start + self.dir * s)
        if self.arrived >= len(self.cubes):
            self.destroy()
            if self.on_done:
                self.on_done()


def pulse(t, speed=4.0):
    """0~1 之间来回变化的值，用来做闪烁高亮。"""
    return 0.5 + 0.5 * math.sin(t * speed)
