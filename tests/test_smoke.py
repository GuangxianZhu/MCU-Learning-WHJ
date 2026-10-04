"""冒烟测试：离屏创建窗口，依次打开每一课，模拟按键并推进若干帧。

运行：python -m pytest tests/  （或直接 python tests/test_smoke.py）
设置环境变量 MCU3D_SHOTS=目录 可以顺便保存每课截图。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from panda3d.core import Filename  # noqa: E402

from mcu3d.app import MCUApp  # noqa: E402
from mcu3d.lessons import LESSONS  # noqa: E402

# 每课要模拟的鼠标点击（物体标签）
PICKS = {0: ["chip"], 1: ["cpu", "uart"], 2: ["bit5"]}

# 每课要模拟的按键（直接调用事件，相当于用户按下）
KEYS = {
    0: ["space", "space", "space", "space", "space"],
    1: ["space"],
    2: ["1", "3", "8", "space", "arrow_left", "a"],
    3: ["1", "4", "b", "space", "space"],
    4: ["space", "arrow_up"],
    5: ["arrow_up", "space", "arrow_down", "f"],
    6: ["shift-a", "space", "arrow_up"],
    7: ["1", "m", "2"],
    8: ["r", "arrow_up", "arrow_left", "r"],
    9: ["h", "arrow_down"],
}

_app = None


def get_app():
    global _app
    if _app is None:
        _app = MCUApp(offscreen=True)
    return _app


def run_frames(app, n, dt=1 / 30):
    for _ in range(n):
        app.step(dt)
        app.graphicsEngine.renderFrame()


def test_menu():
    app = get_app()
    app.show_menu()
    run_frames(app, 3)
    shot(app, "00_menu")


def test_all_lessons():
    app = get_app()
    for i in range(len(LESSONS)):
        app.open_lesson(i)
        run_frames(app, 5)
        for tag in PICKS.get(i, []):
            app.lesson.on_hover(tag)
            app.lesson.on_pick(tag)
            run_frames(app, 10)
        for key in KEYS.get(i, []):
            app.messenger.send(key)
            run_frames(app, 20)
        run_frames(app, 90)
        if i == 3:
            app.messenger.send("b-up")
        if i == 9:
            run_frames(app, 120)   # 继续加热，等温度超过阈值触发报警
            app.messenger.send("h-up")
        app.messenger.send("page_down")
        app.messenger.send("page_up")
        shot(app, "%02d_%s" % (i + 1, LESSONS[i].__name__))
        assert app.lesson is not None
    app.next_lesson()
    app.prev_lesson()
    app.show_menu()
    assert app.lesson is None


def shot(app, name):
    out = os.environ.get("MCU3D_SHOTS")
    if out:
        os.makedirs(out, exist_ok=True)
        app.win.saveScreenshot(Filename.fromOsSpecific(os.path.join(out, name + ".png")))


if __name__ == "__main__":
    test_menu()
    test_all_lessons()
    print("全部课程运行正常")
