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
SIM_PICKS = ["cpu", "sram", "alu", "regfile", "fa3"]
PICKS = {0: ["chip", "button"], 1: ["bit5"], 2: SIM_PICKS, 3: SIM_PICKS, 4: SIM_PICKS,
         5: SIM_PICKS, 6: SIM_PICKS}

# 每课要模拟的按键（直接调用事件，相当于用户按下）
SIM_KEYS = ["t", "t", "space", "space", "r", "arrow_up", "m", "i", "f", "2", "f", "z", "space",
            "tab", "tab"]
KEYS = {
    0: ["space", "space", "space", "space", "space"],
    1: ["1", "3", "8", "space", "arrow_left", "a"],
    2: SIM_KEYS, 3: SIM_KEYS, 4: SIM_KEYS, 5: SIM_KEYS, 6: SIM_KEYS,
    7: ["1", "4", "b", "space", "space"],
    8: ["arrow_up", "space", "arrow_down", "f"],
    9: ["space", "arrow_up"],
    10: ["shift-a", "space", "arrow_up"],
    11: ["1", "m", "2"],
    12: ["r", "arrow_up", "arrow_left", "r"],
    13: ["h", "arrow_down"],
}
GPIO, PROJECT = 7, 13

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
        if i == GPIO:
            app.messenger.send("b-up")
        if i == PROJECT:
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


def test_lesson1_button_lights_led():
    """第 1 课：按键按下 → 程序让 PA5 输出 1 → LED 亮；再点松开 → 灭。"""
    app = get_app()
    app.open_lesson(0)
    run_frames(app, 3)
    lesson = app.lesson
    assert not lesson.led_on
    lesson.on_pick("button")
    run_frames(app, 3)
    assert lesson.led_on and "LED 亮" in lesson.note
    lesson.on_pick("led")
    assert "按键" in lesson.note
    lesson.on_pick("button")
    run_frames(app, 3)
    assert not lesson.led_on


def test_simulator():
    """从一课按 S 打开模拟器，把每个例程都跑一阵，再按 Esc 回到原来那课。"""
    from mcu3d.sim.programs import ORDER
    app = get_app()
    app.open_lesson(3)
    app.messenger.send("s")
    assert app.in_simulator and app.sim_return == 3
    for k in range(len(ORDER)):
        app.messenger.send(str(k + 1))
        for _ in range(3):
            app.messenger.send("arrow_up")      # 调到最快
        app.messenger.send("r")
        run_frames(app, 200)
        app.messenger.send("r")
        assert app.lesson.view.fault is None
        assert app.lesson.view.machine.cpu.count > 5
        shot(app, "sim_%d_%s" % (k + 1, ORDER[k]))
    app.messenger.send("escape")
    assert not app.in_simulator and app.lesson_index == 3
    app.show_menu()
    app.open_simulator()
    run_frames(app, 3)
    app.messenger.send("escape")
    assert app.lesson is None


def test_schematic_levels():
    """模拟器里双击一层层进到与非门，再 Backspace 一层层退回芯片。每层都边跑程序边看。"""
    app = get_app()
    app.open_lesson(5)                      # 第 6 课从 ALU 那一层开始
    schem = app.lesson.view.schem
    assert schem.key == "alu"
    for _ in range(3):
        app.messenger.send("arrow_up")
    app.messenger.send("r")
    run_frames(app, 60)
    app.messenger.send("backspace")
    app.messenger.send("backspace")
    assert schem.key == "chip"
    path = ["cpu", "regfile", "reg3", "dff0"]
    for tag in path:
        app.lesson.on_double_pick(tag)
        run_frames(app, 40)
        shot(app, "lv_%s" % tag)
    assert schem.key == "dff" and len(schem.stack) == 5
    for _ in range(3):
        app.messenger.send("backspace")
    app.lesson.on_double_pick("alu")
    app.lesson.on_double_pick("fa2")
    assert schem.key == "fa"
    run_frames(app, 60)
    shot(app, "lv_fa2")
    app.lesson.on_double_pick("pc")        # 这一层没有 pc，什么都不该发生
    assert schem.key == "fa"
    app.messenger.send("home")
    app.messenger.send("r")
    assert app.lesson.view.fault is None


def test_logic():
    from mcu3d.schem import logic
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                p, s, g, t, co = logic.full_adder(a, b, c)
                assert s + 2 * co == a + b + c
    assert logic.AND(0, None) == 0 and logic.OR(1, None) == 1 and logic.NAND(1, None) is None
    # 锁存器：使能时跟着 D，不使能时保持
    assert logic.latch(1, 1, 0)[3] == 1 and logic.latch(1, 0, 0)[3] == 0


def shot(app, name):
    out = os.environ.get("MCU3D_SHOTS")
    if out:
        os.makedirs(out, exist_ok=True)
        app.win.saveScreenshot(Filename.fromOsSpecific(os.path.join(out, name + ".png")))


if __name__ == "__main__":
    test_menu()
    test_all_lessons()
    test_simulator()
    test_schematic_levels()
    test_logic()
    print("全部课程运行正常")


def test_keypad():
    """屏幕按键：按钮按下发出和实体键一样的消息，换课后按钮跟着换。"""
    from mcu3d.keypad import lesson_keys
    app = get_app()
    app.open_lesson(4)                      # 第 5 课：模拟器类课程
    assert "space" in lesson_keys(app.lesson) and "t" in lesson_keys(app.lesson)
    app.keypad.toggle()
    assert app.keypad.visible and app.keypad.buttons
    view = app.lesson.view
    assert view.cur is None and not view.queue
    app.keypad._press("space")
    app.taskMgr.step()          # 按钮的消息在下一帧的任务里发出
    app.keypad._release("space")
    app.taskMgr.step()
    assert view.cur is not None or view.queue   # 开始执行一条指令了
    run_frames(app, 30)
    shot(app, "keypad_sim")
    app.open_lesson(GPIO)                   # 第 8 课：按住 B 键
    assert "b" in lesson_keys(app.lesson)
    app.keypad._press("b")
    app.taskMgr.step()
    run_frames(app, 10)
    assert app.lesson.idr == 1
    app.keypad._release("b")
    app.taskMgr.step()
    run_frames(app, 10)
    assert app.lesson.idr == 0
    shot(app, "keypad_gpio")
    app.keypad._press("escape")             # 回菜单，按键条收起
    app.taskMgr.step()
    run_frames(app, 3)
    assert app.lesson is None and app.keypad.frame.isHidden()
    app.keypad.toggle()
    assert not app.keypad.visible
