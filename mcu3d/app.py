"""主程序：窗口、相机、鼠标点选、左侧讲解面板、课程菜单。"""

from direct.gui.DirectGui import DGG, DirectButton, DirectFrame
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (AmbientLight, BitMask32, ClockObject,
                          CollisionHandlerQueue,
                          CollisionNode, CollisionRay, CollisionTraverser,
                          DirectionalLight, TextNode, WindowProperties,
                          loadPrcFileData)

from . import glossary, parts, theme, ui
from .lessons import LESSONS, UPCOMING
from .lessons.base import PICK_MASK

PANEL_W = 1.25      # 左侧讲解面板宽度（aspect2d 单位）
BODY_SCALE = 0.042  # 讲解文字大小

GLOBAL_HINTS = ("鼠标：拖动旋转视角，滚轮缩放，左键点选物体\n"
                "讲解太长时：鼠标放在面板上滚动滚轮，或按 PageUp/PageDown\n"
                "Home 重置视角   Tab 隐藏/显示面板\n"
                "[ 上一课   ] 下一课   Esc 课程菜单")

# 右上角“芯片地图”：(标识, 名称, 颜色, 列, 行)，和第 2 课的布局一致
CHIP_MAP = [
    ("cpu", "CPU", theme.CPU, 0, 0), ("nvic", "中断", theme.NVIC, 1, 0),
    ("flash", "Flash", theme.FLASH, 2, 0), ("sram", "SRAM", theme.SRAM, 3, 0),
    ("clock", "时钟", theme.CLOCK, 4, 0),
    ("gpio", "GPIO", theme.GPIO, 0, 1), ("tim", "定时器", theme.TIMER, 1, 1),
    ("uart", "UART", theme.UART, 2, 1), ("i2c", "I2C/SPI", theme.I2C_SPI, 3, 1),
    ("adc", "ADC", theme.ADC, 4, 1),
]
UP_HINT = "……（上面还有，滚轮向上 / PageUp）"
DOWN_HINT = "……（下面还有，滚轮向下 / PageDown）"


class OrbitCamera:
    """围绕观察点旋转的相机。左键拖动、右键/中键拖动都可以旋转。"""

    def __init__(self, base):
        self.base = base
        self.pivot = base.render.attachNewNode("camera-pivot")
        base.camera.reparentTo(self.pivot)
        self.default = (22, 0, -40, (0, 0, 0))
        self.dist, self.h, self.p = 22, 0, -40
        self.button = None
        self.last = None
        self.dragged = False
        for btn in ("mouse2", "mouse3"):
            base.accept(btn, self.start_drag, [btn])
            base.accept(btn + "-up", self.stop_drag, [btn])
        self.apply()

    def set_view(self, dist, h, p, target):
        self.default = (dist, h, p, target)
        self.dist, self.h, self.p = dist, h, p
        self.pivot.setPos(*target)
        self.apply()

    def reset(self):
        self.set_view(*self.default)

    def zoom(self, k):
        self.dist = max(4.0, min(80.0, self.dist * k))
        self.apply()

    def start_drag(self, btn):
        mw = self.base.mouseWatcherNode
        if mw is not None and mw.hasMouse():
            self.button = btn
            self.last = (mw.getMouseX(), mw.getMouseY())
            self.dragged = False

    def stop_drag(self, btn):
        """返回 True 表示这次是拖动（而不是单击）。"""
        if self.button != btn:
            return False
        self.button = None
        return self.dragged

    def update(self):
        mw = self.base.mouseWatcherNode
        if not self.button or mw is None or not mw.hasMouse():
            return
        x, y = mw.getMouseX(), mw.getMouseY()
        dx, dy = x - self.last[0], y - self.last[1]
        if abs(dx) + abs(dy) > 0.004:
            self.dragged = True
        if self.dragged:
            self.h -= dx * 150
            self.p = max(-89, min(5, self.p + dy * 90))
            self.apply()
        self.last = (x, y)

    def apply(self):
        self.pivot.setHpr(self.h, self.p, 0)
        self.base.camera.setPos(0, -self.dist, 0)
        self.base.camera.setHpr(0, 0, 0)


class MCUApp(ShowBase):
    def __init__(self, start_lesson=None, offscreen=False):
        loadPrcFileData("", "window-title MCU 3D 入门课堂\n"
                            "win-size 1280 760\n"
                            "framebuffer-multisample 1\nmultisamples 4\n"
                            "sync-video 1")
        if offscreen:
            loadPrcFileData("", "window-type offscreen\n"
                                "load-display p3tinydisplay\n"
                                "framebuffer-multisample 0\nmultisamples 0\n"
                                "audio-library-name null")
        ShowBase.__init__(self)
        self.disableMouse()
        self.setBackgroundColor(*theme.BG)
        if not offscreen:
            props = WindowProperties()
            props.setTitle("MCU 3D 入门课堂")
            self.win.requestProperties(props)

        self.font = ui.load_font(self.loader)
        self._setup_lights()
        self.orbit = OrbitCamera(self)
        self._setup_picking()
        self._setup_panel()
        self._setup_menu()

        self.lesson = None
        self.lesson_index = None
        self.hover_tag = None
        self.panel_visible = True

        self.accept("escape", self.show_menu)
        self.accept("[", self.prev_lesson)
        self.accept("]", self.next_lesson)
        self.accept("page_up", self.scroll_body, [-8])
        self.accept("page_down", self.scroll_body, [8])
        self.accept("wheel_up", self._wheel, [-1])
        self.accept("wheel_down", self._wheel, [1])
        self.accept("home", self.orbit.reset)
        self.accept("tab", self.toggle_panel)
        self.accept("mouse1", self._mouse1_down)
        self.accept("mouse1-up", self._mouse1_up)

        self.taskMgr.add(self._update, "mcu3d-update")

        if start_lesson is not None and 1 <= start_lesson <= len(LESSONS):
            self.open_lesson(start_lesson - 1)
        else:
            self.show_menu()

    # ------------------------------------------------------------ 场景基础
    def _setup_lights(self):
        amb = AmbientLight("ambient")
        amb.setColor((0.55, 0.55, 0.6, 1))
        self.render.setLight(self.render.attachNewNode(amb))
        sun = DirectionalLight("sun")
        sun.setColor((0.85, 0.82, 0.78, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(30, -60, 0)
        self.render.setLight(sun_np)
        fill = DirectionalLight("fill")
        fill.setColor((0.25, 0.28, 0.35, 1))
        fill_np = self.render.attachNewNode(fill)
        fill_np.setHpr(-150, -30, 0)
        self.render.setLight(fill_np)

    def _setup_picking(self):
        self.picker = CollisionTraverser("picker")
        self.pick_queue = CollisionHandlerQueue()
        node = CollisionNode("mouse-ray")
        node.setFromCollideMask(PICK_MASK)
        node.setIntoCollideMask(BitMask32.allOff())
        self.pick_ray = CollisionRay()
        node.addSolid(self.pick_ray)
        self.picker.addCollider(self.camera.attachNewNode(node), self.pick_queue)

    def pick_under_mouse(self):
        mw = self.mouseWatcherNode
        if self.lesson is None or mw is None or not mw.hasMouse():
            return None
        self.pick_ray.setFromLens(self.camNode, mw.getMouseX(), mw.getMouseY())
        self.picker.traverse(self.lesson.root)
        if self.pick_queue.getNumEntries() == 0:
            return None
        self.pick_queue.sortEntries()
        np = self.pick_queue.getEntry(0).getIntoNodePath().findNetTag("pick")
        return np.getTag("pick") if not np.isEmpty() else None

    def _mouse1_down(self):
        self.orbit.start_drag("mouse1")

    def _mouse1_up(self):
        if self.orbit.stop_drag("mouse1"):
            return  # 拖动旋转，不算点击
        if self.mouse_over_panel():
            return
        tag = self.pick_under_mouse()
        if tag and self.lesson:
            self.lesson.on_pick(tag)

    # ------------------------------------------------------------ 讲解面板
    def _setup_panel(self):
        self.panel = DirectFrame(parent=self.a2dTopLeft,
                                 frameColor=(0.04, 0.05, 0.08, 0.85),
                                 frameSize=(0, PANEL_W, -2.0, 0),
                                 suppressMouse=0)
        self.body_lines = []
        self.body_offset = 0
        self.hint_lines = 1
        self.title_text = OnscreenText(
            parent=self.panel, pos=(0.06, -0.11), scale=0.066,
            align=TextNode.ALeft, font=self.font, fg=theme.ACCENT,
            mayChange=True, text="")
        self.body_text = OnscreenText(
            parent=self.panel, pos=(0.06, -0.21), scale=BODY_SCALE,
            align=TextNode.ALeft, font=self.font, fg=theme.TEXT,
            mayChange=True, text="")
        self.hint_text = OnscreenText(
            parent=self.a2dBottomLeft, pos=(0.06, 0.1), scale=0.034,
            align=TextNode.ALeft, font=self.font, fg=theme.TEXT_DIM,
            mayChange=True, text="")

        self.nav = DirectFrame(parent=self.a2dTopRight, frameColor=(0, 0, 0, 0))
        specs = [("< 上一课", self.prev_lesson, -1.02),
                 ("课程菜单", self.show_menu, -0.66),
                 ("下一课 >", self.next_lesson, -0.30)]
        for text, cmd, x in specs:
            DirectButton(parent=self.nav, text=text, command=cmd,
                         text_font=self.font, scale=0.042, pos=(x, 0, -0.08),
                         frameColor=(0.15, 0.17, 0.24, 0.9), pad=(0.5, 0.3),
                         text_fg=theme.TEXT, relief=DGG.FLAT)

        self._setup_chip_map()

    def _setup_chip_map(self):
        """右上角的芯片地图：亮起的模块就是本课讲的部分。"""
        self.chip_map = DirectFrame(parent=self.a2dTopRight,
                                    frameColor=(0.04, 0.05, 0.08, 0.75),
                                    frameSize=(-0.8, -0.03, -0.43, -0.14))
        OnscreenText(parent=self.chip_map, text="芯片地图：亮的是本课讲的部分",
                     pos=(-0.415, -0.18), scale=0.024, font=self.font,
                     fg=theme.TEXT_DIM)
        self.map_cells = {}
        w, h, gap = 0.138, 0.075, 0.012
        for key, name, color, col, row in CHIP_MAP:
            x0 = -0.775 + col * (w + gap)
            z1 = -0.2 - row * (h + 0.05)
            cell = DirectFrame(parent=self.chip_map, frameColor=color,
                               frameSize=(x0, x0 + w, z1 - h, z1))
            OnscreenText(parent=cell, text=name, pos=(x0 + w / 2, z1 - h / 2 - 0.008),
                         scale=0.023, font=self.font, fg=theme.TEXT)
            self.map_cells[key] = (cell, color)
        self.map_bus = DirectFrame(parent=self.chip_map, frameColor=(0.9, 0.78, 0.4, 1),
                                   frameSize=(-0.775, -0.055, -0.307, -0.293))
        self.map_pins = OnscreenText(parent=self.chip_map, text="", pos=(-0.415, -0.415),
                                     scale=0.022, font=self.font, fg=theme.ACCENT)

    def update_chip_map(self, location):
        everything = "all" in location
        for key, (cell, color) in self.map_cells.items():
            on = everything or key in location
            cell["frameColor"] = color if on else theme.scale(color, 0.22)
        bus_on = everything or "bus" in location
        self.map_bus["frameColor"] = (0.9, 0.78, 0.4, 1) if bus_on else (0.25, 0.22, 0.12, 1)
        self.map_pins.setText("+ 芯片外面的引脚与电路" if (everything or "pins" in location)
                              else "")

    def compose_body(self, text):
        """给每课的讲解加上“在 MCU 的哪里”和“本课新词”。"""
        lesson = self.lesson
        if lesson is None:
            return text
        parts_ = []
        if lesson.location_text:
            parts_.append("【在 MCU 的哪里】\n" + lesson.location_text)
        if text:
            parts_.append(text)
        terms = glossary.explain(lesson.terms)
        if terms:
            parts_.append("【本课新词】\n" + terms)
        return "\n\n".join(parts_)

    def set_body(self, text):
        wrapped = ui.wrap(self.compose_body(text), (PANEL_W - 0.14) / BODY_SCALE)
        self.body_lines = wrapped.split("\n")
        self._render_body()

    def body_capacity(self):
        line_h = BODY_SCALE * self.font.getLineHeight()
        hint_h = 0.06 + self.hint_lines * 0.034 * self.font.getLineHeight()
        return max(5, int((2.0 - 0.21 - hint_h - 0.08) / line_h))

    def _render_body(self):
        cap = self.body_capacity()
        lines = self.body_lines
        max_off = max(0, len(lines) - cap + 2)
        self.body_offset = max(0, min(self.body_offset, max_off))
        off = self.body_offset
        shown = []
        room = cap
        if off > 0:
            shown.append(UP_HINT)
            room -= 1
        rest = lines[off:]
        if len(rest) > room:
            shown += rest[:room - 1] + [DOWN_HINT]
        else:
            shown += rest
        self.body_text.setText("\n".join(shown))

    def scroll_body(self, delta):
        if self.lesson is None:
            return
        self.body_offset += delta
        self._render_body()

    def mouse_over_panel(self):
        mw = self.mouseWatcherNode
        if (self.lesson is None or not self.panel_visible or mw is None
                or not mw.hasMouse()):
            return False
        return (mw.getMouseX() + 1) * self.getAspectRatio() < PANEL_W

    def _wheel(self, direction):
        if self.mouse_over_panel():
            self.scroll_body(3 * direction)
        else:
            self.orbit.zoom(1.1 if direction > 0 else 0.9)

    def set_hints(self, text):
        text = ui.wrap(text, (PANEL_W - 0.14) / 0.034)
        n = text.count("\n") + 1
        self.hint_lines = n
        self.hint_text.setText(text)
        self.hint_text.setPos(0.06, 0.06 + (n - 1) * 0.034 * 1.2)

    def toggle_panel(self):
        if self.lesson is None:
            return
        self.panel_visible = not self.panel_visible
        for w in (self.panel, self.hint_text):
            w.show() if self.panel_visible else w.hide()

    # ------------------------------------------------------------ 课程菜单
    def _setup_menu(self):
        self.menu = DirectFrame(parent=self.aspect2d,
                                frameColor=(0.03, 0.04, 0.07, 0.72),
                                frameSize=(-4, 4, -1, 1))
        OnscreenText(parent=self.menu, text="MCU 3D 入门课堂", pos=(0, 0.8),
                     scale=0.1, font=self.font, fg=theme.ACCENT)
        OnscreenText(parent=self.menu, pos=(0, 0.7), scale=0.045,
                     font=self.font, fg=theme.TEXT_DIM,
                     text="零基础，从“芯片里面有什么”开始。点击一课开始学习。")
        z = 0.55
        rows = [(i, cls.title, cls.summary, True) for i, cls in enumerate(LESSONS)]
        rows += [(len(LESSONS) + k, t, s, False) for k, (t, s) in enumerate(UPCOMING)]
        for i, title, summary, ready in rows:
            text = "第 %d 课   %s   ·   %s" % (i + 1, title, summary)
            if not ready:
                text += "（制作中）"
            DirectButton(parent=self.menu, text=text, text_font=self.font,
                         text_align=TextNode.ALeft, scale=0.045,
                         pos=(-1.3, 0, z), frameSize=(-1, 58, -0.6, 1.2),
                         frameColor=((0.13, 0.16, 0.24, 0.95) if ready
                                     else (0.1, 0.1, 0.12, 0.8)),
                         text_fg=theme.TEXT if ready else theme.TEXT_DIM,
                         relief=DGG.FLAT,
                         command=self.open_lesson if ready else None,
                         extraArgs=[i] if ready else [],
                         state=DGG.NORMAL if ready else DGG.DISABLED)
            z -= 0.115
        OnscreenText(parent=self.menu, pos=(0, -0.9), scale=0.035,
                     font=self.font, fg=theme.TEXT_DIM,
                     text="进入课程后：[ 上一课  ] 下一课  Esc 回到菜单")

        self.menu_scene = self.render.attachNewNode("menu-scene")
        parts.Chip(self.menu_scene, size=5, label="MCU")

    def show_menu(self):
        self._close_lesson()
        self.menu.show()
        self.menu_scene.show()
        self.panel.hide()
        self.hint_text.hide()
        self.nav.hide()
        self.chip_map.hide()
        self.orbit.set_view(16, 20, -35, (0, 0, 0))

    # ------------------------------------------------------------ 课程切换
    def _close_lesson(self):
        if self.lesson is not None:
            self.lesson.destroy()
            self.lesson = None
            self.hover_tag = None

    def open_lesson(self, index):
        self._close_lesson()
        self.menu.hide()
        self.menu_scene.hide()
        self.nav.show()
        self.chip_map.show()
        if self.panel_visible:
            self.panel.show()
            self.hint_text.show()
        self.lesson_index = index
        cls = LESSONS[index]
        self.lesson = cls(self)
        self.title_text.setText("第 %d 课  %s" % (index + 1, cls.title))
        self.body_offset = 0
        self.update_chip_map(cls.location)
        hints = cls.hints.strip()
        self.set_hints((hints + "\n\n" if hints else "") + GLOBAL_HINTS)
        self.set_body("")
        self.orbit.set_view(*cls.camera)
        self.lesson.setup()

    def next_lesson(self):
        if self.lesson_index is None:
            self.open_lesson(0)
        else:
            self.open_lesson((self.lesson_index + 1) % len(LESSONS))

    def prev_lesson(self):
        if self.lesson_index is None:
            self.open_lesson(len(LESSONS) - 1)
        else:
            self.open_lesson((self.lesson_index - 1) % len(LESSONS))

    # ------------------------------------------------------------ 每帧更新
    def _update_film_offset(self):
        # 面板挡住了左边一块，把 3D 画面的中心往右挪一点
        lens = self.camLens
        if self.lesson is not None and self.panel_visible:
            frac = PANEL_W / (2 * self.getAspectRatio())
            lens.setFilmOffset(-lens.getFilmSize()[0] * frac / 2, 0)
        else:
            lens.setFilmOffset(0, 0)

    def step(self, dt):
        """推进一帧逻辑（测试里也会直接调用）。"""
        self.orbit.update()
        self._update_film_offset()
        if self.lesson is None:
            self.menu_scene.setH(self.menu_scene.getH() + 15 * dt)
            return
        tag = self.pick_under_mouse()
        if tag != self.hover_tag:
            self.hover_tag = tag
            self.lesson.on_hover(tag)
        self.lesson._tick(dt)

    def _update(self, task):
        dt = min(ClockObject.getGlobalClock().getDt(), 0.1)
        self.step(dt)
        return task.cont


def run(start_lesson=None):
    MCUApp(start_lesson).run()
