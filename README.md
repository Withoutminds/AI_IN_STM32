# 基于 STM32N6 的端侧手势识别与实时控制

摄像头看手，STM32N6570-DK 在本地做 INT8 推理，舵机转到对应角度。图像不上传。

| 手势               | 文件夹名 | 舵机角度 |
| ------------------ | -------- | -------- |
| 向左               | `left`   | 0°       |
| 向上               | `up`     | 45°      |
| 停止（握拳或掌心） | `stop`   | 90°      |
| 向下               | `down`   | 135°     |
| 向右               | `right`  | 180°     |

置信度低于 0.70 保持上一姿态。连续 3 帧同一类才更新 PWM。

## 硬件

- STM32N6570-DK 与套件摄像头
- SG90 一类舵机：信号接 Arduino D9（PE14，TIM1_CH4），5 V 和 GND 接 Arduino 的 +5V 与 GND
- USB Type-C 同时供电和提供 USART1 虚拟串口，115200 8N1

工具版本按 ST 当前图像分类教程：STM32CubeIDE 2.0+、STM32CubeMX 6.17+、STM32CubeN6 1.3+、STM32Cube AI Studio 1.2+（ST Edge AI Core 4.0）、STM32CubeProgrammer 2.22+。主机训练用 Python 3.12 或 3.13，依赖见 `host/requirements.txt`。

## 1. 官方基线

克隆 [STM32N6-GettingStarted-ImageClassification](https://github.com/STMicroelectronics/STM32N6-GettingStarted-ImageClassification)，不要放进本仓库。

```text
cd Application/STM32N6570-DK
make flash_weights
make flash
```

`make flash_weights` 烧 `Model/STM32N6570-DK/network_data.hex`。`make flash` 签名应用并写到 `0x70100000`。需要 `STM32_Programmer_CLI` 和外部 loader `MX66UW1G45G_STM32N6570-DK.stldr` 在 PATH 里。CubeIDE 工程在 `Application/STM32N6570-DK/STM32CubeIDE`。

上电后 USART1 打印版本横幅，屏幕打印类别和 `Inference: N ms`。官方模型是 `efficientnet_v2B1_240_fft_qdq_int8`，101 类，不是手势网络。把屏幕上的推理时间和构建日志里的内存填进 `baseline/metrics.csv` 的 `official` 行：

```text
python host/parse_board_log.py --stage official --memory baseline/official_size.txt
```

`official_size.txt` 贴上 CubeIDE 的 `Memory region` 或 `arm-none-eabi-size` 输出。FLASH 列是 text+data，RAM 列是 data+bss。权重在外部 NOR，大小另记 `weights_bytes`。

验收：摄像头有画面，串口有横幅，屏幕上的推理时间是稳定的毫秒数。

## 2. 数据和模型

真实照片放在：

```text
host/data/train/left|up|stop|down|right
host/data/val/...
host/data/test/...
host/data/outlier
host/data/unknown
```

固定机位和距离。每类大约 200 张进 train，并留出验证集。`test` 要换人或换光照。`outlier` 是训练时用的非手势图（空手、桌面、噪声），标签是五类均匀分布，用来把置信度压下去。`unknown` 是没参与训练的另一批非手势图，只用来算拒识率。训练前删掉 `host/data/SYNTHETIC.txt`，报告里才会标成 collected。

还没有照片时，可以先生成合成图，只为了把导出跑通：

```text
python host/make_synthetic_dataset.py
python host/train_and_export.py --weights none --epochs 8
```

正式训练把 `--weights none` 换成 `--weights imagenet`，轮数加大。脚本读 `deploy/gesture_labels.txt`，结构是 MobileNetV2 α=0.35，输入 128×128，图内做 `(x/127.5)-1`。产物：

- `host/artifacts/gesture_fp32.tflite`
- `host/artifacts/gesture_int8.tflite`
- `host/artifacts/train_summary.json`
- `host/artifacts/eval_report.json`

INT8 文件的输入是 int8，输出是 float 概率，方便官方 `main.c` 按 float 做排序。论文表用 `eval_report.json` 里的 accuracy、tflite 字节数和参数量。PC 上的 `mean_invoke_ms` 不是板端时间。

## 3. 上板和舵机

`deploy/deployment_n6.yaml` 指向 INT8 模型和 `STM32N6570-DK`。把 Getting Started 克隆到 `third_party/STM32N6-GettingStarted-ImageClassification`，改 yaml 里的 `stedgeai.exe` 和 `stm32cubeide.exe` 路径。在 Model Zoo 的 image classification 目录运行部署前，把 `model_path` 和 `classes_file_path` 改成绝对路径。

类别表、Makefile、TIM 开关和 `main.c` 插入点写在 `firmware/notes.md`。表决和 PWM 源码在 `firmware/Inc` 与 `firmware/Src`。

## 4. 实验

协议在 `eval/protocol.md`。主机侧先跑：

```text
python host/test_gesture_vote.py
```

板端日志每帧一行 `class= conf= infer_ms= angle= moved=`，再用 `host/parse_board_log.py` 写回 `baseline/metrics.csv`。

端到端毫秒数按 `(3-1)*帧周期 + 推理毫秒 + 舵机转动毫秒` 计算。对比表决和单帧直驱时，数 `moved=1` 的次数。
