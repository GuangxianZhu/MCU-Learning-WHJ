"""用“芯片内部模拟器”上课的基类，以及可以从任何一课打开的自由模拟器。"""

from ..sim.programs import ORDER, PROGRAMS
from ..sim.view import MODULES, SimView, program_menu_text
from .base import Lesson

SIM_HINTS = ("空格 执行一条指令   T 只走一拍   R 连续运行/暂停\n"
             "上下方向键 调速度   Z 复位重来   M 切换内存表\n"
             "左键点 3D 模块看介绍，I 回到课文")


class SimLesson(Lesson):
    """画面就是模拟器。子类写 intro（课文）和 programs（第一个是默认例程）。"""

    programs = ["inc"]
    intro = ""
    sim_layout = True
    show_chip_map = False
    camera = (36, 0, -60, (0, -0.6, 0))

    @classmethod
    def lesson_hints(cls):
        extra = ""
        if len(cls.programs) > 1:
            extra = "\n换例程：" + program_menu_text(cls.programs)
        return SIM_HINTS + extra

    @property
    def sim_program(self):
        return self.programs[0]

    def setup(self):
        self.view = SimView(self, self.programs[0], on_beat=self.on_beat)
        self.view.bind_keys(self, self.programs if len(self.programs) > 1 else None)
        self.accept("i", self.show_intro)
        self.show_intro()

    def show_intro(self):
        self.set_body(self.intro)

    def on_beat(self, beat):
        """每播放一拍都会调用，子类可以在这里加讲解。"""

    def on_pick(self, tag):
        if tag in MODULES:
            title, desc = MODULES[tag]
            self.set_body("【%s】\n%s\n\n（按 I 回到课文）" % (title, desc))

    def update(self, dt):
        self.view.update(dt)

    def destroy(self):
        self.view.destroy()
        Lesson.destroy(self)


class SimulatorLesson(SimLesson):
    """自由模式：所有例程都能选。从菜单或任何一课按 S 打开。"""

    title = "芯片内部模拟器"
    summary = "看 CPU 一条一条执行程序"
    programs = ORDER
    location = ["cpu", "flash", "sram", "bus"]
    location_text = ("CPU 内核（寄存器组、标志位、控制单元、ALU）、系统总线，"
                     "以及 Flash、SRAM 两种存储器。外设会在第 8 课起陆续接进来。")
    terms = ["寄存器组", "ALU", "标志位", "总线", "地址线", "数据线", "读写控制线"]

    def __init__(self, app, program=None):
        SimLesson.__init__(self, app)
        self.first = program if program in PROGRAMS else ORDER[0]

    def setup(self):
        SimLesson.setup(self)
        if self.first != self.programs[0]:
            self.view.load(self.first)

    @property
    def intro(self):
        lines = ["这是一颗简化的 ARM Cortex-M 芯片（按 STM32F103 的地址），"
                 "CPU 真的会从 Flash 取出机器码、自己译码、自己执行。",
                 "",
                 "画面中间是芯片内部：下面是 CPU，往上是三组总线线路，再往上是 Flash、SRAM 和外设区。"
                 "右边是 C 代码和对应的汇编、机器码，下面是寄存器表和内存表。"
                 "屏幕下方写着“这一拍”在做什么、总线上传的是什么、ALU 怎么一位一位地算。",
                 "",
                 "【例程】按数字键切换："]
        for k, key in enumerate(ORDER):
            p = PROGRAMS[key]
            lines.append("%d  %s：%s" % (k + 1, p.title, p.summary))
        lines += ["", "按 Esc 或 S 回到刚才的课。"]
        return "\n".join(lines)
