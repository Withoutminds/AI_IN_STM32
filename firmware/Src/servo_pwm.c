#include "stm32n6xx_hal.h"
#include "servo_pwm.h"

static TIM_HandleTypeDef htim_servo;

void HAL_TIM_PWM_MspInit(TIM_HandleTypeDef *htim)
{
  GPIO_InitTypeDef gpio = {0};

  if (htim->Instance != TIM1) {
    return;
  }

  __HAL_RCC_TIM1_CLK_ENABLE();
  __HAL_RCC_GPIOE_CLK_ENABLE();

  /* PE14 = Arduino D9 = TIM1_CH4 (AF1). Not used by the camera, USART1, or XSPI. */
  gpio.Pin = GPIO_PIN_14;
  gpio.Mode = GPIO_MODE_AF_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_LOW;
  gpio.Alternate = GPIO_AF1_TIM1;
  HAL_GPIO_Init(GPIOE, &gpio);
}

static uint32_t Servo_TimerClockHz(void)
{
  /* Application/STM32N6570-DK SystemClock_Config sets APB2 prescaler to 1,
   * so TIM1 clock equals HCLK (200 MHz in that clock tree). */
  return HAL_RCC_GetHCLKFreq();
}

void Servo_Init(void)
{
  TIM_OC_InitTypeDef oc = {0};
  TIM_BreakDeadTimeConfigTypeDef break_dt = {0};
  uint32_t timclk = Servo_TimerClockHz();
  uint32_t prescaler = (timclk / 1000000U) - 1U;

  htim_servo.Instance = TIM1;
  htim_servo.Init.Prescaler = prescaler;
  htim_servo.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim_servo.Init.Period = 20000U - 1U;
  htim_servo.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim_servo.Init.RepetitionCounter = 0;
  htim_servo.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_PWM_Init(&htim_servo) != HAL_OK) {
    while (1) {
    }
  }

  oc.OCMode = TIM_OCMODE_PWM1;
  oc.Pulse = 1500;
  oc.OCPolarity = TIM_OCPOLARITY_HIGH;
  oc.OCNPolarity = TIM_OCNPOLARITY_HIGH;
  oc.OCFastMode = TIM_OCFAST_DISABLE;
  oc.OCIdleState = TIM_OCIDLESTATE_RESET;
  oc.OCNIdleState = TIM_OCNIDLESTATE_RESET;
  if (HAL_TIM_PWM_ConfigChannel(&htim_servo, &oc, TIM_CHANNEL_4) != HAL_OK) {
    while (1) {
    }
  }

  break_dt.OffStateRunMode = TIM_OSSR_DISABLE;
  break_dt.OffStateIDLEMode = TIM_OSSI_DISABLE;
  break_dt.LockLevel = TIM_LOCKLEVEL_OFF;
  break_dt.DeadTime = 0;
  break_dt.BreakState = TIM_BREAK_DISABLE;
  break_dt.BreakPolarity = TIM_BREAKPOLARITY_HIGH;
  break_dt.BreakFilter = 0;
  break_dt.AutomaticOutput = TIM_AUTOMATICOUTPUT_ENABLE;
  if (HAL_TIMEx_ConfigBreakDeadTime(&htim_servo, &break_dt) != HAL_OK) {
    while (1) {
    }
  }

  if (HAL_TIM_PWM_Start(&htim_servo, TIM_CHANNEL_4) != HAL_OK) {
    while (1) {
    }
  }
}

void Servo_SetAngle(uint16_t angle_deg)
{
  uint32_t pulse_us;

  if (angle_deg > 180U) {
    angle_deg = 180U;
  }
  pulse_us = 500U + ((uint32_t)angle_deg * 2000U) / 180U;
  __HAL_TIM_SET_COMPARE(&htim_servo, TIM_CHANNEL_4, pulse_us);
}
