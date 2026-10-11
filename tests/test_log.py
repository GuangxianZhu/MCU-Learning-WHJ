"""日志：启动信息、操作记录、Panda3D 的警告和程序崩溃时的报错都要写进 logs/ 里的文件。

每个用例在单独的子进程里跑，因为日志会接管 sys.stdout / sys.excepthook。
"""

import glob
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_script(code):
    folder = tempfile.mkdtemp(prefix="mcu3d-log-")
    env = dict(os.environ, MCU3D_LOG_DIR=folder, PYTHONIOENCODING="utf-8")
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    files = glob.glob(os.path.join(folder, "mcu3d-*.log"))
    assert len(files) == 1, (files, proc.stdout, proc.stderr)
    with open(files[0], encoding="utf-8") as f:
        return proc, f.read()


def test_crash_is_logged():
    proc, text = run_script(
        "from mcu3d import log\n"
        "log.setup()\n"
        "print('你好 hello')\n"
        "raise ValueError('boom')\n")
    assert proc.returncode != 0
    assert "Python:" in text and "Panda3D:" in text
    assert "[输出] 你好 hello" in text
    assert "ValueError: boom" in text and "Traceback" in text
    assert text.count("ValueError: boom") == 1          # 不能记两遍
    assert "ValueError: boom" in proc.stderr            # 黑窗口里也要看得到
    assert "请把这个文件发给 Claude" in proc.stderr


def test_app_events_are_logged():
    proc, text = run_script(
        "from mcu3d import log\n"
        "log.setup()\n"
        "log.capture_panda_notify()\n"
        "from mcu3d.app import MCUApp\n"
        "from panda3d.core import TexturePool\n"
        "app = MCUApp(offscreen=True)\n"
        "log.log_graphics(app)\n"
        "app.open_lesson(0)\n"
        "app._log_button('space')\n"
        "app.lesson.on_pick('button')\n"
        "app.open_simulator('inc')\n"
        "for _ in range(4):\n"
        "    app.lesson.view.step_instruction()\n"
        "TexturePool.loadTexture('no-such-file.png')\n"
        "app.step(0.03)\n"
        "log.shutdown()\n")
    assert proc.returncode == 0, proc.stderr
    assert "打开 第 1 课" in text
    assert "按键 space" in text
    assert "打开 芯片内部模拟器 inc" in text
    assert "电路图：整颗芯片" in text
    assert "模拟器：执行 复位" in text and "模拟器：执行 0x08" in text
    assert "[Panda3D]" in text and "no-such-file" in text
    assert "==== 结束" in text


def test_log_folder_is_pruned():
    from mcu3d import log
    folder = tempfile.mkdtemp(prefix="mcu3d-log-")
    for i in range(log.KEEP + 5):
        open(os.path.join(folder, "mcu3d-20260101-0000%02d.log" % i), "w").close()
    log._prune(folder)
    left = sorted(os.listdir(folder))
    assert len(left) == log.KEEP and left[-1].endswith("%02d.log" % (log.KEEP + 4))


if __name__ == "__main__":
    test_crash_is_logged()
    test_app_events_are_logged()
    test_log_folder_is_pruned()
    print("ok")
