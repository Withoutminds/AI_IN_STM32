#ifndef GESTURE_CONTROL_H
#define GESTURE_CONTROL_H

#include <stdint.h>

#define GESTURE_CLASS_COUNT 5
#define GESTURE_VOTE_FRAMES 3
#define GESTURE_CONFIDENCE_MIN 0.70f

/* Same order as deploy/gesture_labels.txt. */
typedef enum {
  GESTURE_LEFT = 0,
  GESTURE_UP = 1,
  GESTURE_STOP = 2,
  GESTURE_DOWN = 3,
  GESTURE_RIGHT = 4
} GestureClass;

typedef struct {
  uint8_t streak_class;
  uint8_t streak_count;
  uint8_t held_class;
  uint8_t holding;
} GestureControl;

void Gesture_Init(GestureControl *ctrl);
uint16_t Gesture_Angle(uint8_t class_id);

/* Writes the angle the servo should already be holding.
 * Returns 1 only when that angle changes. */
int Gesture_Update(GestureControl *ctrl, uint8_t class_id, float confidence, uint16_t *angle_deg);

#endif
