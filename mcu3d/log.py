"""运行日志：把“这次打开课程都发生了什么”写进 logs/ 文件夹。

每次启动写一个新文件 logs/mcu3d-年月日-时分秒.log，只留最近 KEEP 个。
里面有：电脑环境（系统、Python、Panda3D、显卡）、打开了哪一课、按了哪些键、
点了什么、模拟器执行了哪些指令，以及程序出错时的完整报错（traceback）。
Panda3D 自己（C++ 部分）打印的警告和 print() 的提示也会一起收进来。

出问题时把最新的那个 .log 文件发给 Claude 就行。
"""

import glob
import logging
import os
import platform
import sys
import threading
import time
import traceback

KEEP = 20                     # 最多保留多少次运行的日志
MAX_BYTES = 5 * 1024 * 1024   # 单个文件超过这么大就不再记按键这类细节，防止开着不关撑满硬盘

log = logging.getLogger("mcu3d")
log.addHandler(logging.NullHandler())   # 没调用 setup()（比如跑测试）时什么都不写
path = None                   # 这次运行的日志文件（没开日志时是 None）
_handler = None
_notify_stream = None


def default_dir():
    """优先放在项目文件夹里（和 Start-MCU3D.bat 同一层），写不进去就放用户目录。"""
    env = os.environ.get("MCU3D_LOG_DIR")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def _writable_dir(first):
    for d in (first, os.path.join(os.path.expanduser("~"), ".mcu3d", "logs")):
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".write-test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return d
        except OSError:
            continue
    return None


def _prune(folder):
    files = sorted(glob.glob(os.path.join(folder, "mcu3d-*.log")))
    for old in files[:-KEEP]:
        try:
            os.remove(old)
        except OSError:
            pass


class _SizeLimit(logging.Filter):
    """文件太大以后只记 WARNING 以上（报错永远记）。"""

    def filter(self, record):
        if record.levelno >= logging.WARNING or _handler is None:
            return True
        try:
            return _handler.stream.tell() < MAX_BYTES
        except (OSError, ValueError, AttributeError):
            return True


class _Tee:
    """让 print() 的内容既显示在黑窗口里，也写进日志。"""

    def __init__(self, stream, level):
        self.stream = stream
        self.level = level
        self.buf = ""
        self.busy = False

    def write(self, s):
        if self.stream is not None:
            try:
                self.stream.write(s)
            except Exception:
                pass
        if self.busy:           # 写日志本身出错时 logging 会往 stderr 打印，别绕回来
            return len(s)
        self.busy = True
        try:
            self.buf += s
            while "\n" in self.buf:
                line, self.buf = self.buf.split("\n", 1)
                if line.strip():
                    log.log(self.level, "[输出] %s", line)
        finally:
            self.busy = False
        return len(s)

    def flush(self):
        if self.stream is not None:
            try:
                self.stream.flush()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self.stream, name)


def setup(folder=None, tee=True):
    """打开日志文件。失败（比如没有写权限）也不影响课程本身运行。"""
    global path, _handler
    if _handler is not None:
        return path
    log.setLevel(logging.DEBUG)
    folder = _writable_dir(folder or default_dir())
    if folder is None:
        return None
    _prune(folder)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(folder, "mcu3d-%s.log" % stamp)
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(folder, "mcu3d-%s-%d.log" % (stamp, n))
    try:
        _handler = logging.FileHandler(path, encoding="utf-8")
    except OSError:
        path = None
        return None
    _handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-7s %(message)s",
                                            "%H:%M:%S"))
    _handler.addFilter(_SizeLimit())
    log.addHandler(_handler)
    log.propagate = False

    sys.excepthook = _excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = lambda a: _excepthook(a.exc_type, a.exc_value, a.exc_traceback)
    if tee:
        sys.stdout = _Tee(sys.stdout, logging.INFO)
        sys.stderr = _Tee(sys.stderr, logging.WARNING)
    log.info("==== MCU 3D 入门课堂 启动 ====")
    log_environment()
    return path


def log_environment():
    log.info("时间: %s", time.strftime("%Y-%m-%d %H:%M:%S %z"))
    log.info("系统: %s (%s)", platform.platform(), platform.machine())
    log.info("Python: %s  %s", sys.version.replace("\n", " "), sys.executable)
    log.info("启动参数: %s", sys.argv)
    log.info("当前文件夹: %s", os.getcwd())
    try:
        from panda3d.core import PandaSystem
        log.info("Panda3D: %s", PandaSystem.getVersionString())
    except Exception as e:      # 没装 Panda3D 时也要把这件事记下来
        log.error("Panda3D 导入失败: %r", e)


def log_graphics(base):
    """窗口打开以后再记显卡、窗口大小这些信息。"""
    try:
        gsg = base.win.getGsg()
        log.info("显卡: %s / %s / OpenGL %s", gsg.getDriverVendor(), gsg.getDriverRenderer(),
                 gsg.getDriverVersion())
    except Exception as e:
        log.info("显卡信息读取失败: %r", e)
    try:
        log.info("窗口: %dx%d  屏幕: %dx%d", base.win.getXSize(), base.win.getYSize(),
                 base.pipe.getDisplayWidth(), base.pipe.getDisplayHeight())
    except Exception:
        pass


def capture_panda_notify():
    """把 Panda3D C++ 部分的警告（比如 :display(error)）也收进日志。"""
    global _notify_stream
    if _handler is None:
        return
    try:
        from panda3d.core import LineStream, Notify
        _notify_stream = LineStream()
        Notify.ptr().setOstreamPtr(_notify_stream, False)
    except Exception as e:
        log.info("没法接管 Panda3D 的输出: %r", e)
        _notify_stream = None


def poll_panda_notify():
    """每帧调用一次：把 Panda3D 新打印的几行转到日志和黑窗口。"""
    s = _notify_stream
    if s is None:
        return
    while s.isTextAvailable():
        line = s.getLine()
        if line.strip():
            low = line.lower()
            level = logging.ERROR if "error" in low else (
                logging.WARNING if "warning" in low else logging.INFO)
            log.log(level, "[Panda3D] %s", line)
            if level >= logging.WARNING:
                _print_console(line)


def _print_console(line):
    stream = sys.__stderr__
    if stream is not None:
        try:
            stream.write(line + "\n")
        except Exception:
            pass


def _excepthook(etype, value, tb):
    poll_panda_notify()         # 先把 Panda3D 最后打印的几行（往往就是出错原因）记下来
    log_exception("程序出错（没有被处理的异常）", (etype, value, tb))
    out = sys.__stderr__
    if out is not None:         # 直接写黑窗口，不经过 _Tee，免得日志里记两遍
        try:
            traceback.print_exception(etype, value, tb, file=out)
            out.write("\n程序出错了。%s\n请把这个文件发给 Claude。\n" % where_text())
            out.flush()
        except Exception:
            pass


def log_exception(what, exc_info=None):
    exc_info = exc_info or sys.exc_info()
    text = "".join(traceback.format_exception(*exc_info))
    log.error("%s\n%s", what, text.rstrip())
    flush()


def flush():
    if _handler is not None:
        try:
            _handler.flush()
        except Exception:
            pass


def shutdown(reason="正常退出"):
    poll_panda_notify()
    log.info("==== 结束：%s ====", reason)
    flush()


def where_text():
    """给界面和黑窗口用的一句话：日志在哪。"""
    if path is None:
        return "这次没有写日志（日志文件夹没有写入权限）。"
    return "日志文件：%s" % path


def open_folder():
    """用系统的文件管理器打开日志文件夹。"""
    if path is None:
        return False
    folder = os.path.dirname(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(folder)    # noqa: 只在 Windows 上有
        elif sys.platform == "darwin":
            os.spawnlp(os.P_NOWAIT, "open", "open", folder)
        else:
            os.spawnlp(os.P_NOWAIT, "xdg-open", "xdg-open", folder)
        log.info("打开了日志文件夹")
        return True
    except Exception as e:
        log.info("打开日志文件夹失败: %r", e)
        return False
