# 实验记录

主机侧数字来自 `host/artifacts/eval_report.json`。板端数字在烧录后填进 `baseline/metrics.csv`，不要把 PC 上的 `mean_invoke_ms` 写成 NPU 时间。

## 已经能在 PC 上完成的对比

- FP32 与 INT8 的测试准确率、混淆矩阵、文件大小、单次调用时间
- 置信度低于 0.70 的比例，以及只统计被接受帧时的准确率
- `unknown/` 里非手势图像的拒识率
- 同一串预测上，「单帧就改角度」和「3 帧表决」的舵机动作次数

`host/test_gesture_vote.py` 固定检查：满 3 帧才动、低置信度清零、换类重新计数、表决动作次数少于单帧直驱。

## 合成数据上已经算出的数

`host/artifacts/eval_report.json` 这次是合成图，不是论文数字。FP32 和 INT8 在 80 张测试图上的准确率都是 1.0。INT8 文件 645712 字节，FP32 文件 1636928 字节。参数量 416613。没参与训练的 `unknown` 拒识率是 1.0（置信度阈值 0.70）。

干净的分类块上，表决和单帧直驱都是 5 次改角度。插入单帧误判后，表决 5 次，单帧直驱 15 次。PC 上 INT8 平均调用约 0.36 ms，这不是 NPU 时间。

## 板子上要补的数

串口每帧一行：

```text
class=left conf=0.910 infer_ms=12 angle=0 moved=1
```

把日志存成 `baseline/gesture_uart.txt`，构建输出存成 `baseline/gesture_size.txt`，然后：

```text
python host/parse_board_log.py --stage gesture_int8 --serial baseline/gesture_uart.txt --memory baseline/gesture_size.txt
```

官方基线没有这行日志。屏幕上的 `Inference: N ms` 手抄进 `baseline/metrics.csv` 的 `official` 行。构建日志里的 `Memory region` 或 `arm-none-eabi-size` 的 text/data/bss 用同一脚本、`--stage official` 写入。`network_data.hex` 的字节数填到 `weights_bytes`。权在外部 NOR，不在 ELF 的 FLASH 里。

帧率按串口时间戳或 `1000 / infer_ms` 估算。官方循环是抓一帧再推理，所以帧周期包含采集，大于单独的推理时间。

端到端时延（画面变了到舵机到位）：

```text
(3 - 1) * 帧周期 + 推理毫秒 + 舵机转动毫秒
```

帧周期和推理从串口得到。舵机转动用秒表，从 `moved=1` 那一行到舵机停稳。对比两组：表决开启，以及把 `GESTURE_VOTE_FRAMES` 临时改成 1 的单帧直驱。数串口里 `moved=1` 的次数，抖动多的那组动作更多。

拒识在板子上另做三组，每组至少 20 秒：空手、另一只手、侧光。统计 `conf` 低于 0.70 的帧比例，以及这些帧里 `moved` 必须为 0。

测试集不要和训练集是同一只手、同一种光。合成图只证明导出和表决脚本能跑通。
