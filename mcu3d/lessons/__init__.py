"""课程注册表：菜单和“上一课/下一课”都按这里的顺序。"""

from .l01_what_is_mcu import WhatIsMCU
from .l02_architecture import Architecture
from .l03_binary_register import BinaryRegister
from .l04_gpio import GPIOLesson
from .l05_clock_interrupt import ClockInterrupt
from .l06_timer_pwm import TimerPWM
from .l07_uart import UARTLesson

LESSONS = [
    WhatIsMCU,
    Architecture,
    BinaryRegister,
    GPIOLesson,
    ClockInterrupt,
    TimerPWM,
    UARTLesson,
]

# 还没做 3D 演示的课程（菜单里显示为“制作中”），格式：(标题, 一句话简介)
UPCOMING = [
    ("I2C 与 SPI", "两根线挂一串设备 / 四根线高速传输"),
    ("ADC 模数转换", "把温度、光线变成数字"),
    ("综合项目", "做一个温度报警器"),
]
