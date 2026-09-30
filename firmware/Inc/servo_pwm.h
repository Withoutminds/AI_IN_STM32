#ifndef SERVO_PWM_H
#define SERVO_PWM_H

#include <stdint.h>

/* Arduino D9 on STM32N6570-DK: PE14, TIM1_CH4, AF1.
 * 50 Hz, pulse 500 us at 0 degrees and 2500 us at 180 degrees. */
void Servo_Init(void);
void Servo_SetAngle(uint16_t angle_deg);

#endif
