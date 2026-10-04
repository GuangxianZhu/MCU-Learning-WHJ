"""每一课的基类。

新增一课的步骤：
1. 在 lessons/ 下新建 lXX_xxx.py，继承 Lesson；
2. 填写 title / summary / hints，在 setup() 里搭场景，在 update(dt) 里做动画；
3. 在 lessons/__init__.py 的 LESSONS 列表里加上它。
"""

from direct.showbase.DirectObject import DirectObject
from panda3d.core import BitMask32

from .. import shapes, theme
from ..ui import text3d

PICK_MASK = BitMask32.bit(5)


class Lesson(DirectObject):
    title = "未命名"
    summary = ""
    hints = ""
    # 本课讲的是 MCU 的哪些部分（右上角芯片地图会亮起）：
    # cpu nvic flash sram clock gpio tim uart i2c adc bus pins，或 all
    location = []
    location_text = ""     # 面板开头“在 MCU 的哪里”的说明
    link_text = ""         # “承上启下”：用到前面哪课的什么，后面哪课会用到本课
    apply_text = ""        # “学了能做什么”
    terms = []             # 面板最后“本课新词”要解释的术语（见 glossary.py）
    sim_program = "inc"    # 按 S 打开芯片内部模拟器时先载入的例程
    show_chip_map = True   # 右上角是否显示芯片地图
    sim_layout = False     # True：画面右边和下方是模拟器的数据面板
    # 相机初始视角：(距离, 水平角, 俯仰角, 观察点)
    camera = (22, 0, -40, (0, 0, 0))

    @classmethod
    def lesson_hints(cls):
        return cls.hints

    def __init__(self, app):
        DirectObject.__init__(self)
        self.app = app
        self.root = app.render.attachNewNode(type(self).__name__)
        self.time = 0.0
        self.movers = []

    # ---- 子类重写 ----
    def setup(self):
        pass

    def update(self, dt):
        pass

    def on_pick(self, tag):
        """鼠标左键点中了带 tag 的物体。"""

    def on_hover(self, tag):
        """鼠标悬停的物体变化时调用，tag 可能为 None。"""

    # ---- 框架调用 ----
    def _tick(self, dt):
        self.time += dt
        for m in list(self.movers):
            m.update(dt)
            if m.done:
                self.movers.remove(m)
        self.update(dt)

    def clear_movers(self):
        """立刻删掉所有还在移动的数据包。"""
        for m in self.movers:
            m.destroy()
        self.movers.clear()

    def destroy(self):
        self.ignoreAll()
        self.root.removeNode()

    # ---- 便捷工具 ----
    def set_body(self, text):
        self.app.set_body(text)

    def box(self, size, pos=(0, 0, 0), color=(1, 1, 1, 1), parent=None,
            pick=None):
        np = shapes.box(size, color)
        np.reparentTo(parent or self.root)
        np.setPos(*pos)
        if pick:
            self.make_pickable(np, pick)
        return np

    def label(self, text, pos, scale=0.5, color=theme.TEXT, parent=None,
              **kw):
        return text3d(text, parent or self.root, pos, scale, color, **kw)

    def wire(self, points, color=theme.WIRE_IDLE, thickness=3.0, parent=None):
        np = shapes.lines(points, color, thickness)
        np.reparentTo(parent or self.root)
        np.setLightOff(1)
        return np

    def make_pickable(self, np, tag):
        np.setTag("pick", tag)
        np.setCollideMask(PICK_MASK)

    def accept_keys(self, keys, func, extra=()):
        """同时绑定按下与长按重复事件。extra 是传给 func 的参数列表。"""
        for k in keys:
            self.accept(k, func, list(extra))
            self.accept(k + "-repeat", func, list(extra))
