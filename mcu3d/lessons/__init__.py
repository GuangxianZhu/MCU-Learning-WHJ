"""课程注册表：菜单和“上一课/下一课”都按这里的顺序。"""

from .l01_what_is_mcu import WhatIsMCU
from .l02_architecture import Architecture
from .l03_binary_register import BinaryRegister
from .l04_gpio import GPIOLesson
from .l05_clock_interrupt import ClockInterrupt
from .l06_timer_pwm import TimerPWM
from .l07_uart import UARTLesson
from .l08_i2c_spi import I2CSPILesson
from .l09_adc import ADCLesson
from .l10_project import ProjectLesson

LESSONS = [
    WhatIsMCU,
    Architecture,
    BinaryRegister,
    GPIOLesson,
    ClockInterrupt,
    TimerPWM,
    UARTLesson,
    I2CSPILesson,
    ADCLesson,
    ProjectLesson,
]

# 还没做 3D 演示的课程（菜单里显示为“制作中”），格式：(标题, 一句话简介)
UPCOMING = []
