"""Confidence gate and 3-frame vote. Matches firmware/Src/gesture_control.c."""

CLASS_NAMES = ("left", "up", "stop", "down", "right")
ANGLES = (0, 45, 90, 135, 180)
VOTE_FRAMES = 3
CONFIDENCE_MIN = 0.70


class GestureControl:
    def __init__(self, vote_frames=VOTE_FRAMES, confidence_min=CONFIDENCE_MIN):
        self.vote_frames = vote_frames
        self.confidence_min = confidence_min
        self.streak_class = 2
        self.streak_count = 0
        self.held_class = 2
        self.holding = 1

    def angle(self, class_id=None):
        if class_id is None:
            class_id = self.held_class
        if class_id < 0 or class_id >= len(ANGLES):
            return ANGLES[2]
        return ANGLES[class_id]

    def update(self, class_id, confidence):
        if confidence < self.confidence_min or class_id < 0 or class_id >= len(ANGLES):
            self.streak_count = 0
            return False, self.angle()

        if self.streak_count == 0 or class_id != self.streak_class:
            self.streak_class = class_id
            self.streak_count = 1
        elif self.streak_count < 255:
            self.streak_count += 1

        if self.streak_count >= self.vote_frames:
            self.streak_count = self.vote_frames
            if class_id != self.held_class or self.holding == 0:
                self.held_class = class_id
                self.holding = 1
                return True, self.angle(class_id)

        return False, self.angle()
