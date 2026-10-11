"""屏幕按键条：不用实体键盘也能操作（手机远程桌面、平板触屏时用）。

原理：Panda3D 里按一个键，其实就是往“消息中心”(messenger) 发一条名字叫
"space"、"t" 之类的消息，课程用 accept("space", ...) 收这条消息。
屏幕上的按钮按下时发同名消息、松开时发 "名字-up"，效果和按实体键完全一样，
所以每课不用改任何代码。按钮列表在每次打开一课时，从这课收哪些消息自动生成。
"""

from direct.gui.DirectGui import DGG, DirectButton, DirectFrame

from . import log as applog
from . import theme

# 按键在按钮上显示的名字
LABELS = {
    "space": "空格", "backspace": "Backspace 上一层", "enter": "Enter 进入",
    # 字体里没有箭头符号，用汉字
    "arrow_up": "方向 上", "arrow_down": "方向 下", "arrow_left": "方向 左",
    "arrow_right": "方向 右",
    "escape": "Esc 菜单", "tab": "Tab 面板", "s": "S 模拟器", "home": "Home 复位",
    "page_up": "讲解上翻", "page_down": "讲解下翻", "wheel_up": "放大", "wheel_down": "缩小",
    "[": "[ 上一课", "]": "] 下一课",
}
# 每课都有的全局按键（第二行）
GLOBAL_KEYS = ["page_up", "page_down", "wheel_up", "wheel_down", "home",
               "tab", "s", "escape"]
# 这些键在别的键存在时只是别名，不重复显示
ALIASES = {"=": "arrow_up", "-": "arrow_down"}
SKIP = ("mouse", "wheel", "shift-", "control-", "alt-")
MAX_LESSON_KEYS = 18   # 第 11 课收 a~z、0~9，全摆出来太挤，只摆前面一部分

BTN_SCALE = 0.04
ROW_H = 0.085
GAP = 0.012
SORT = 100       # 画在其它面板上面


FIRST = ["space", "enter", "backspace", "arrow_up", "arrow_down",
         "arrow_left", "arrow_right"]


def _order(key):
    # 常用特殊键在前，然后数字，然后字母
    if key in FIRST:
        return (0, "%02d" % FIRST.index(key))
    if len(key) > 1:
        return (0, key)
    return (1 if key.isdigit() else 2, key)


def lesson_keys(lesson):
    """从这一课注册过的消息里挑出“按键”，按显示顺序返回。"""
    events = set(lesson.getAllAccepting())
    keys = []
    for ev in events:
        if ev.endswith("-up") or ev.endswith("-repeat") or ev.startswith(SKIP):
            continue
        if ev in ALIASES and ALIASES[ev] in events:
            continue
        keys.append(ev)
    keys.sort(key=_order)
    return keys[:MAX_LESSON_KEYS]


def label_of(key):
    return LABELS.get(key, key.upper())


class KeyPad:
    """屏幕底部中间的按键条，右下角“屏幕按键”按钮打开/收起。"""

    def __init__(self, app, visible=False):
        self.app = app
        self.visible = visible
        self.frame = DirectFrame(parent=app.a2dBottomCenter,
                                 frameColor=(0.04, 0.05, 0.08, 0.92),
                                 sortOrder=SORT)
        self.buttons = []
        self.toggle_btn = DirectButton(
            parent=app.a2dBottomRight, text="屏幕按键", command=self.toggle,
            text_font=app.font, scale=BTN_SCALE, pos=(-0.13, 0, 0.04),
            frameColor=(0.15, 0.17, 0.24, 0.95), pad=(0.4, 0.25),
            text_fg=theme.TEXT, relief=DGG.FLAT, sortOrder=SORT)
        # sortOrder 只决定谁先接住鼠标；画的先后还要放进“弹出层”这个绘制队列
        for w in (self.frame, self.toggle_btn):
            w.setBin("gui-popup", 50)
        self.keys = []

    def toggle(self):
        self.visible = not self.visible
        self.refresh(self.keys)

    def refresh(self, keys):
        """keys 是这一课的按键；None 表示在课程菜单里（不显示按键条）。"""
        self.keys = keys
        for b in self.buttons:
            b.destroy()
        self.buttons = []
        if not self.visible or keys is None:
            self.frame.hide()
            self.toggle_btn["text"] = "屏幕按键"
            return
        self.toggle_btn["text"] = "收起按键"
        max_w = min(2 * self.app.getAspectRatio() - 0.5, 2.4)
        lines = self._lines(keys, max_w) + self._lines(GLOBAL_KEYS, max_w)
        width = max(sum(w for _, w in ln) + GAP * (len(ln) - 1) for ln in lines)
        for k, line in enumerate(lines):
            z = 0.025 + (len(lines) - 1 - k) * ROW_H + ROW_H / 2
            total = sum(w for _, w in line) + GAP * (len(line) - 1)
            x = -total / 2
            for b, w in line:
                b.setPos(x - b.getBounds()[0] * BTN_SCALE, 0, z - 0.012)
                x += w + GAP
        half = width / 2 + 0.02
        self.frame["frameSize"] = (-half, half, 0, 0.03 + len(lines) * ROW_H)
        self.frame.show()

    def _lines(self, keys, max_w):
        """给一组键做按钮，按宽度折成几行；返回 [[(按钮, 宽度), ...], ...]。"""
        lines, line, used = [], [], 0.0
        for key in keys:
            b = DirectButton(parent=self.frame, text=label_of(key),
                             text_font=self.app.font, scale=BTN_SCALE,
                             frameColor=(0.18, 0.21, 0.3, 1), pad=(0.45, 0.3),
                             text_fg=theme.TEXT, relief=DGG.FLAT)
            # 按下发 key，松开发 key-up：“按住 B”这类长按操作也能用
            b.bind(DGG.B1PRESS, self._press, [key])
            b.bind(DGG.B1RELEASE, self._release, [key])
            self.buttons.append(b)
            w = (b.getBounds()[1] - b.getBounds()[0]) * BTN_SCALE
            if line and used + GAP + w > max_w:
                lines.append(line)
                line, used = [], 0.0
            used += (GAP if line else 0) + w
            line.append((b, w))
        if line:
            lines.append(line)
        return lines

    # 下一帧再发消息：Esc、S 这类键会换课、把按键条重建，
    # 不能在按钮自己的点击回调里把按钮删掉
    def _press(self, key, _event=None):
        self.app.taskMgr.add(self._send, "keypad-press", extraArgs=[key])

    def _release(self, key, _event=None):
        self.app.taskMgr.add(self._send, "keypad-release", extraArgs=[key + "-up"])

    def _send(self, event):
        if not event.endswith("-up"):
            applog.log.debug("屏幕按键 %s", event)
        self.app.messenger.send(event)
        # 返回 None：这个任务只跑一次
