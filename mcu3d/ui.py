"""中文字体加载与文字工具。

Panda3D 自带字体不含中文，所以要找一个系统里的中文字体。
查找顺序：环境变量 MCU3D_FONT → assets/fonts/ 目录 → 各系统常见字体。
"""

import glob
import os
import re

from panda3d.core import BillboardEffect, Filename, TextNode

_HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_FONTS = os.path.join(os.path.dirname(_HERE), "assets", "fonts")

SYSTEM_FONTS = [
    # Windows
    "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/wenquanyi/wqy-zenhei/wqy-zenhei.ttc",
]

_font = None


def find_font_path():
    env = os.environ.get("MCU3D_FONT")
    if env and os.path.exists(env):
        return env
    for ext in ("ttf", "otf", "ttc"):
        found = sorted(glob.glob(os.path.join(ASSET_FONTS, "*." + ext)))
        if found:
            return found[0]
    for path in SYSTEM_FONTS:
        if os.path.exists(path):
            return path
    return None


def load_font(loader):
    """加载中文字体，找不到时退回默认字体并打印提示。"""
    global _font
    path = find_font_path()
    if path:
        font = loader.loadFont(Filename.fromOsSpecific(path).getFullpath())
        if font and font.isValid():
            font.setPixelsPerUnit(64)
            _font = font
            return font
    print("[提示] 没找到中文字体，中文会显示成方块。"
          "请把任意中文 .ttf/.otf 字体放进 assets/fonts/ 目录，"
          "或设置环境变量 MCU3D_FONT=字体路径。")
    _font = TextNode.getDefaultFont()
    return _font


def get_font():
    return _font


def text3d(text, parent, pos=(0, 0, 0), scale=0.5, color=(1, 1, 1, 1),
           align="center", billboard=True, wordwrap=None):
    """在 3D 场景里放一段文字。billboard=True 时文字总是面向相机。"""
    tn = TextNode("text")
    if _font is not None:
        tn.setFont(_font)
    tn.setText(text)
    tn.setTextColor(*color)
    tn.setAlign({"center": TextNode.ACenter, "left": TextNode.ALeft,
                 "right": TextNode.ARight}[align])
    if wordwrap:
        tn.setWordwrap(wordwrap)
    tn.setShadow(0.04, 0.04)
    tn.setShadowColor(0, 0, 0, 0.8)
    np = parent.attachNewNode(tn)
    np.setPos(*pos)
    np.setScale(scale)
    np.setLightOff(1)
    # 文字最后画、不写深度，避免和阴影或物体表面闪烁打架
    np.setBin("fixed", 10)
    np.setDepthWrite(False)
    if billboard:
        np.setEffect(BillboardEffect.makePointEye())
    return np


def set_text(np, text):
    np.node().setText(text)


def flat_text(text, parent, pos=(0, 0, 0), scale=0.5, color=(1, 1, 1, 1),
              align="center"):
    """平躺在物体表面上的文字（例如印在芯片上的字）。"""
    np = text3d(text, parent, pos, scale, color, align, billboard=False)
    np.setP(-90)
    np.node().setShadow(0, 0)
    return np


_TOKEN = re.compile(r"[A-Za-z0-9_\-.,:;()<>=&|^~+*/%'\"#!?\[\]{}]+|\s|.")
_NO_LINE_START = set("，。、；：！？）》”’」』,.;:!?)")


def _char_width(c):
    if c == " ":
        return 0.3
    return 1.0 if ord(c) > 0x2E7F else 0.55


def wrap(text, width):
    """按显示宽度折行：中文字算 1，英文数字算约 0.55，英文单词不拆开。

    Panda3D 自带的 wordwrap 只在空格处断行，对中文效果不好，所以自己算。
    """
    out = []
    for para in text.split("\n"):
        line, w = "", 0.0
        for tok in _TOKEN.findall(para):
            tw = sum(_char_width(c) for c in tok)
            if w + tw > width and line.strip() and tok not in _NO_LINE_START:
                out.append(line.rstrip())
                if tok.isspace():
                    line, w = "", 0.0
                else:
                    line, w = tok, tw
            else:
                line += tok
                w += tw
        out.append(line.rstrip())
    return "\n".join(out)
