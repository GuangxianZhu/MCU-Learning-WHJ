"""课程注册表：菜单、路线图和“上一课/下一课”都按这里的顺序。"""

from .l01_what_is_mcu import WhatIsMCU
from .l02_binary_register import BinaryRegister
from .l03_memory import MemoryLesson
from .l04_bus import BusLesson
from .l05_cpu import CPULesson
from .l06_alu import ALULesson
from .l07_stack import StackLesson
from .l08_gpio import GPIOLesson
from .l09_timer_pwm import TimerPWM
from .l10_clock_interrupt import ClockInterrupt
from .l11_uart import UARTLesson
from .l12_i2c_spi import I2CSPILesson
from .l13_adc import ADCLesson
from .l14_project import ProjectLesson
from .sim_lesson import SimulatorLesson  # noqa: F401  自由模拟器，不在课程列表里

__all__ = ["LESSONS", "STAGES", "UPCOMING", "SimulatorLesson", "stage_of"]

LESSONS = [
    WhatIsMCU,
    BinaryRegister,
    MemoryLesson,
    BusLesson,
    CPULesson,
    ALULesson,
    StackLesson,
    GPIOLesson,
    TimerPWM,
    ClockInterrupt,
    UARTLesson,
    I2CSPILesson,
    ADCLesson,
    ProjectLesson,
]

# 五个阶段：(名称, 说明, 包含的课程下标)
STAGES = [
    ("阶段 0", "全景", [0]),
    ("阶段 1", "数据的语言", [1]),
    ("阶段 2", "CPU 与存储（模拟器核心）", [2, 3, 4, 5, 6]),
    ("阶段 3", "控制外部世界", [7, 8, 9]),
    ("阶段 4", "通信与感知", [10, 11, 12]),
    ("阶段 5", "综合项目", [13]),
]


def stage_of(index):
    for k, (_, _, members) in enumerate(STAGES):
        if index in members:
            return k
    return None


# 还没做 3D 演示的课程（菜单里显示为“制作中”），格式：(标题, 一句话简介)
UPCOMING = []
