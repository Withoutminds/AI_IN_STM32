# 接到官方图像分类工程

固件改动落在 [STM32N6-GettingStarted-ImageClassification](https://github.com/STMicroelectronics/STM32N6-GettingStarted-ImageClassification) 的 `Application/STM32N6570-DK`。本目录的 `.c/.h` 拷进去，不要把整份 ST 工程克隆进本仓库。

类别顺序必须与 `deploy/gesture_labels.txt` 一致：`left up stop down right`，对应舵机 `0 45 90 135 180` 度。

## 引脚

| 信号 | 连接 |
| --- | --- |
| 舵机信号 | Arduino D9，MCU 为 PE14，TIM1_CH4，AF1 |
| 舵机电源 | Arduino +5V |
| 舵机地 | Arduino GND，与板子共地 |
| 串口 | USART1，PE5 TX，PE6 RX，115200。ST-Link 虚拟串口即可 |

PE14 在 UM3300 上是 D9，不承担摄像头 CSI、USART1 或 XSPI。摄像头仍走板载 DCMIPP。舵机信号是 3.3 V，SG90 可以接。若 USB 供电时板子复位，把舵机 5 V 改到独立电源，地仍然连到板子。

上电脉宽 1500 us，舵机停在 90 度（停止）。

## 拷贝文件

把本目录下的文件拷到官方工程：

- `firmware/Inc/gesture_control.h` → `Application/STM32N6570-DK/Inc/`
- `firmware/Inc/servo_pwm.h` → `Application/STM32N6570-DK/Inc/`
- `firmware/Src/gesture_control.c` → `Application/STM32N6570-DK/Src/`
- `firmware/Src/servo_pwm.c` → `Application/STM32N6570-DK/Src/`

`Application/STM32N6570-DK/Makefile` 的 C sources 增加：

```make
C_SOURCES += Src/gesture_control.c
C_SOURCES += Src/servo_pwm.c
C_SOURCES += ../../STM32Cube_FW_N6/Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_tim.c
C_SOURCES += ../../STM32Cube_FW_N6/Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_tim_ex.c
```

官方 `Inc/stm32n6xx_hal_conf.h` 里 `HAL_TIM_MODULE_ENABLED` 是注释掉的。删掉行首 `//`，否则 `stm32n6xx_hal_tim.h` 不会被包含。

CubeIDE 工程要同样把这两个源文件和 TIM 驱动加进工程。若 CubeMX 已经生成了 `HAL_TIM_PWM_MspInit`，删掉 `servo_pwm.c` 里的同名函数，把其中 PE14 初始化挪进已有的 MSP 函数，避免重复定义。

## 换类别表

编辑 `Application/STM32N6570-DK/Inc/app_config.h`，替换官方 Food-101 的 101 类：

```c
#define NB_CLASSES (5)
#define CLASSES_TABLE const char* classes_table[NB_CLASSES] = {\
  "left",\
  "up",\
  "stop",\
  "down",\
  "right"}

#define WELCOME_MSG_1 "gesture_mobilenetv2_a035_128_int8"
#define WELCOME_MSG_2 "Servo follows a 3-frame vote"
```

`ASPECT_RATIO_MODE` 保持 `ASPECT_RATIO_CROP`，`COLOR_MODE` 保持 `COLOR_RGB`，与 `deploy/deployment_n6.yaml` 一致。

## 换网络

用 ST Edge AI Core 4.0 按 `deploy/deployment_n6.yaml` 生成网络，或在 STM32Cube AI Studio 里选板 `STM32N6570-DK`、模型 `host/artifacts/gesture_int8.tflite`。

生成物替换官方工程的：

- `Model/STM32N6570-DK/network.c`
- `Model/STM32N6570-DK/network_ecblobs.h`
- `Model/STM32N6570-DK/stai_network.c`
- `Model/STM32N6570-DK/stai_network.h`
- `Model/STM32N6570-DK/network_data.hex`

权重要单独烧。官方 Makefile 的目标是 `make flash_weights`，地址和外部 loader 以该工程为准。应用本身是 `make flash`（签名后写到 `0x70100000`）。

`main.c` 里 `Network_Postprocess` 把输出当成 `float` 概率。ST Edge AI 的运行时会对量化输出做反量化，保持这个写法。若串口里的置信度不在 0 到 1，说明新网络的输出缓冲仍是 int8，要用 `stai_network` 信息里的 scale 和 zero_point 先换算成 float，再交给 `Gesture_Update`。

## 改 main.c

在 include 区增加：

```c
#include "gesture_control.h"
#include "servo_pwm.h"
```

在 `nn_top1_output_class_proba` 旁边增加类别下标。`Bubblesort` 会打乱概率数组，类别号只留在 `ranking[0]`，必须在 `Network_Postprocess` 里存下来：

```c
uint8_t nn_top1_output_class_index;
static GestureControl gesture_ctrl;
```

`Network_Postprocess` 末尾：

```c
nn_top1_output_class_name = classes_table[ranking[0]];
nn_top1_output_class_proba = *((float *) (pp_input));
nn_top1_output_class_index = (uint8_t)ranking[0];
```

`main` 里 `LCD_init()` 之后、进入 `while (1)` 之前：

```c
Gesture_Init(&gesture_ctrl);
Servo_Init();
```

`while` 循环里，`Network_Postprocess()` 之后、`Display_NetworkOutput` 之前：

```c
uint16_t angle_deg = 90;
int moved = Gesture_Update(&gesture_ctrl,
                           nn_top1_output_class_index,
                           nn_top1_output_class_proba,
                           &angle_deg);
if (moved) {
  Servo_SetAngle(angle_deg);
}
printf("class=%s conf=%.3f infer_ms=%lu angle=%u moved=%d\r\n",
       nn_top1_output_class_name,
       nn_top1_output_class_proba,
       (unsigned long)(ts[1] - ts[0]),
       (unsigned)angle_deg,
       moved);
```

`printf` 已经经 `_write` 发到 USART1。官方屏幕上的 `Inference: %ums` 仍保留，基线阶段可以不改循环，只读屏幕。

## 表决

置信度低于 0.70，或类别号非法：连续计数清零，舵机保持上一角度。连续 3 帧是同一类才更新 PWM。上电视为已经停在 `stop` / 90 度，所以开机不会先抖一下。逻辑与 `host/gesture_vote.py` 相同，主机侧单测覆盖了这条状态机。
