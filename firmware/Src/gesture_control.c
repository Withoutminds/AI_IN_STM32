#include "gesture_control.h"

static const uint16_t kAngles[GESTURE_CLASS_COUNT] = {0, 45, 90, 135, 180};

void Gesture_Init(GestureControl *ctrl)
{
  ctrl->streak_class = GESTURE_STOP;
  ctrl->streak_count = 0;
  ctrl->held_class = GESTURE_STOP;
  ctrl->holding = 1;
}

uint16_t Gesture_Angle(uint8_t class_id)
{
  if (class_id >= GESTURE_CLASS_COUNT) {
    return kAngles[GESTURE_STOP];
  }
  return kAngles[class_id];
}

int Gesture_Update(GestureControl *ctrl, uint8_t class_id, float confidence, uint16_t *angle_deg)
{
  if (confidence < GESTURE_CONFIDENCE_MIN || class_id >= GESTURE_CLASS_COUNT) {
    ctrl->streak_count = 0;
    if (angle_deg != 0) {
      *angle_deg = Gesture_Angle(ctrl->held_class);
    }
    return 0;
  }

  if (ctrl->streak_count == 0 || class_id != ctrl->streak_class) {
    ctrl->streak_class = class_id;
    ctrl->streak_count = 1;
  } else if (ctrl->streak_count < 255) {
    ctrl->streak_count++;
  }

  if (ctrl->streak_count >= GESTURE_VOTE_FRAMES) {
    ctrl->streak_count = GESTURE_VOTE_FRAMES;
    if (class_id != ctrl->held_class || ctrl->holding == 0) {
      ctrl->held_class = class_id;
      ctrl->holding = 1;
      if (angle_deg != 0) {
        *angle_deg = Gesture_Angle(class_id);
      }
      return 1;
    }
  }

  if (angle_deg != 0) {
    *angle_deg = Gesture_Angle(ctrl->held_class);
  }
  return 0;
}
