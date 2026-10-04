# MCU 3D 入门课堂

零基础学单片机（MCU）：用 [Panda3D](https://www.panda3d.org/) 做的交互式 3D 课程，
把芯片内部“看不见”的东西——寄存器、总线、中断、串口比特——变成可以旋转、点击、动手玩的 3D 场景。

📖 **课程大纲与每课要点**：[docs/课程大纲.md](docs/课程大纲.md)

![课堂截图](docs/images/preview.png)

## 快速开始

需要 Python 3.8 或更新版本。

```bash
pip install -r requirements.txt   # 安装 Panda3D
python -m mcu3d                   # 打开课程菜单
python -m mcu3d 4                 # 直接进入第 4 课
```

> 中文显示成方块？见 [assets/fonts/README.md](assets/fonts/README.md)。

## 课程列表（第一版）

| 课 | 主题 | 你会在 3D 里看到 |
|---|---|---|
| 1 | 什么是 MCU | 揭开芯片外壳，看到里面的 CPU、存储器、外设；LED 闪烁 |
| 2 | 内部构造 | 芯片内部模块与总线，一条“点灯指令”的数据流动画 |
| 3 | 二进制与寄存器 | 8 个比特方块，按键翻转、计数、移位，实时换算十进制/十六进制 |
| 4 | GPIO 输入输出 | 写 ODR 点亮 8 个 LED、读按键 IDR，流水灯等程序与对应 C 代码 |
| 5 | 时钟与中断 | 时钟波形、PC 指针执行主程序，按键触发中断、栈的压入弹出 |
| 6 | 定时器与 PWM | 计数器柱子、ARR/CCR 比较、更新事件、占空比改变 LED 亮度 |
| 7 | UART 串口通信 | 键盘打字，比特沿导线传输，波形图与接收寄存器逐位拼出字符 |
| 8–10 | I2C/SPI、ADC、综合项目 | 制作中（大纲里已有文字要点） |

## 操作方式

- **鼠标**：左键拖动或右键拖动旋转视角，滚轮缩放，左键单击选中物体
- **键盘**：`[` 上一课，`]` 下一课，`Esc` 课程菜单，`Home` 重置视角，`Tab` 隐藏/显示讲解面板
- 每课自己的按键写在左下角提示里（例如空格、数字键）

## 项目结构

```
mcu3d/
  app.py          主程序：窗口、相机、点选、讲解面板、菜单
  ui.py           中文字体加载、3D 文字、中文折行
  shapes.py       程序生成的几何体（方块、圆柱、导线），不依赖模型文件
  parts.py        可复用元件：芯片、LED、按键、波形图、数据包
  theme.py        配色表
  lessons/
    base.py       每课的基类 Lesson
    l01_...py     第 1~7 课
    __init__.py   课程注册表（顺序、制作中的课程）
docs/课程大纲.md  完整大纲、要点、小练习
tests/            离屏冒烟测试
```

### 想改课程 / 加新课？

1. 改讲解文字：直接编辑对应 `lessons/lXX_*.py` 里的中文字符串。
2. 加新课：复制一个现有课程文件，继承 `Lesson`，在 `setup()` 里搭场景、`update(dt)` 里做动画，
   然后加到 `lessons/__init__.py` 的 `LESSONS` 列表（并从 `UPCOMING` 里删掉对应条目）。
3. 改配色：编辑 `theme.py`。

## 测试

```bash
pip install pytest
python -m pytest tests/                                   # 离屏打开每一课并模拟按键
MCU3D_SHOTS=screenshots python tests/test_smoke.py        # 顺便保存每课截图
```
