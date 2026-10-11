"""入口：python -m mcu3d [课号]"""

import argparse

from . import log as applog


def main():
    parser = argparse.ArgumentParser(description="MCU 3D 入门课堂")
    parser.add_argument("lesson", nargs="?", type=int, default=None,
                        help="直接打开第几课（从 1 开始），不填则显示课程菜单")
    parser.add_argument("--keys", action="store_true",
                        help="一开始就显示屏幕按键（手机远程桌面、触屏时用）")
    args = parser.parse_args()
    # 先打开日志再导入 Panda3D：这样连“Panda3D 没装好”这种错也能记下来
    applog.setup()
    from .app import run
    run(args.lesson, keypad=args.keys)


if __name__ == "__main__":
    main()
