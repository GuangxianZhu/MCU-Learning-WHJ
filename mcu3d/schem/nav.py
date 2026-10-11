"""在各层电路图之间走动：双击方块进入下一层，Backspace 回到上一层。

屏幕下方“这一拍”说明的上面有一行位置提示（像 Logisim 左边的电路列表），
再下面是导线颜色的图例。
"""

from direct.gui.DirectGui import DGG, DirectButton, DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode

from .. import log as applog
from .. import theme
from ..sim.asm import REG_NAMES
from ..ui import colored, get_font
from .draw import Canvas
from .sheets import SHEETS

# 从某一层开始时，上面各层的路径（这样 Backspace 能一层层退回芯片）
PATHS = {
    "chip": [("chip", None)],
    "cpu": [("chip", None), ("cpu", None)],
    "regfile": [("chip", None), ("cpu", None), ("regfile", None)],
    "alu": [("chip", None), ("cpu", None), ("alu", None)],
}

LEGEND = ("导线 " + colored("green", "亮绿=1") + "  " + colored("dkgreen", "深绿=0") + "  " +
          colored("blue", "蓝=悬空") + "  粗线=多位总线  " + colored("hi", "橙=这一拍在用"))


def crumb(key, param):
    if key == "reg":
        return "寄存器 %s" % REG_NAMES[param]
    if key == "dff":
        return "%s 的 bit%d" % (REG_NAMES[param[0]], param[1])
    if key == "fa":
        return "bit%d 全加器" % param
    return {"chip": "整颗芯片", "cpu": "CPU 内核", "regfile": "寄存器组", "alu": "ALU"}[key]


class Schematic:
    def __init__(self, lesson, start="chip", strip=None):
        self.lesson = lesson
        self.app = lesson.app
        self.stack = list(PATHS.get(start, PATHS["chip"]))
        self.canvas = None
        self.sheet = None
        self.state = None
        self.selected = None
        self.on_change = None       # 换了一层电路图时调用（课程可以借机改讲解）
        self._build_ui(strip)
        self.open()

    # ---------------------------------------------------------------- 界面
    def _build_ui(self, strip):
        x0, w = strip or (-0.8, 1.6)
        font = get_font()
        self.frame = DirectFrame(parent=self.app.a2dBottomCenter,
                                 frameColor=(0.04, 0.05, 0.08, 0.92),
                                 frameSize=(x0, x0 + w, 0.505, 0.615))
        self.path_text = OnscreenText(parent=self.frame, pos=(x0 + 0.02, 0.578), scale=0.028,
                                      align=TextNode.ALeft, font=font, fg=theme.ACCENT,
                                      mayChange=True, text="")
        self.legend = OnscreenText(parent=self.frame, pos=(x0 + 0.02, 0.53), scale=0.023,
                                   align=TextNode.ALeft, font=font, fg=theme.TEXT,
                                   mayChange=True, text=LEGEND)
        self.up_btn = DirectButton(parent=self.frame, text="↑ 上一层", text_font=font,
                                   scale=0.028, pos=(x0 + w - 0.08, 0, 0.575),
                                   frameColor=(0.2, 0.22, 0.3, 1), text_fg=theme.TEXT,
                                   relief=DGG.FLAT, pad=(0.3, 0.15), command=self.up)

    def destroy(self):
        if self.canvas is not None:
            self.canvas.destroy()
        self.frame.destroy()

    # ---------------------------------------------------------------- 导航
    @property
    def key(self):
        return self.stack[-1][0]

    def open(self):
        if self.canvas is not None:
            self.canvas.destroy()
        key, param = self.stack[-1]
        self.canvas = Canvas(self.lesson)
        x0, z0, x1, z1 = SHEETS[key].bounds
        self.canvas.paper(x0 - 1, z0 - 1, x1 + 1, z1 + 1)
        self.sheet = SHEETS[key](self.canvas, param)
        self.selected = None
        if self.state is not None:
            self.sheet.apply(self.state)
        names = [crumb(k, p) for k, p in self.stack]
        self.path_text.setText("位置：" + " > ".join(names))
        applog.log.info("电路图：%s", " > ".join(names))
        if len(self.stack) > 1:
            self.up_btn.show()
        else:
            self.up_btn.hide()
        self.fit()
        if self.on_change:
            self.on_change(key)

    def fit(self):
        self.app.fit_view(*self.sheet.bounds)

    def go(self, key, param=None):
        """直接跳到某一层（按 PATHS 补上上面各层）。"""
        self.stack = list(PATHS.get(key, PATHS["chip"]))
        if key not in PATHS:
            self.stack.append((key, param))
        self.open()

    def enter(self, tag=None):
        tag = tag or self.selected
        info = self.sheet.picks.get(tag)
        if not info or not info[2]:
            return False
        self.stack.append(info[2])
        self.open()
        return True

    def up(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self.open()

    def describe(self, tag):
        """单击时给讲解面板用：(名称, 介绍, 能不能进入)。"""
        info = self.sheet.picks.get(tag)
        if info is None:
            return None
        self.selected = tag
        return info[0], info[1], info[2] is not None

    # ---------------------------------------------------------------- 状态
    def apply(self, state):
        self.state = state
        self.sheet.apply(state)
