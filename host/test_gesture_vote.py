"""State-machine checks shared with firmware/Src/gesture_control.c."""

from gesture_vote import GestureControl


def check(condition, message):
    if not condition:
        raise SystemExit(message)


def test_three_frames_move_once():
    ctrl = GestureControl()
    moved = [ctrl.update(0, 0.91)[0] for _ in range(4)]
    check(moved == [False, False, True, False], f"vote edges {moved}")
    check(ctrl.angle() == 0, "left is 0 degrees")


def test_low_confidence_resets_streak():
    ctrl = GestureControl()
    ctrl.update(0, 0.95)
    ctrl.update(0, 0.95)
    moved, angle = ctrl.update(0, 0.69)
    check(moved is False and angle == 90, "reject keeps the stop pose")
    ctrl.update(0, 0.95)
    ctrl.update(0, 0.95)
    moved, _ = ctrl.update(0, 0.95)
    check(moved is True, "streak restarts after a reject")


def test_class_change_restarts_vote():
    ctrl = GestureControl()
    ctrl.update(0, 0.9)
    ctrl.update(0, 0.9)
    moved, angle = ctrl.update(1, 0.9)
    check(moved is False and angle == 90, "a new class does not inherit the streak")
    ctrl.update(1, 0.9)
    moved, angle = ctrl.update(1, 0.9)
    check(moved is True and angle == 45, "up is 45 degrees")


def test_direct_drive_chatters_more_than_vote():
    frames = [0, 0, 0, 1, 0, 0, 0, 4, 4, 0, 0, 0]
    voted = GestureControl()
    vote_moves = 0
    direct_moves = 0
    direct_hold = 2
    for class_id in frames:
        if voted.update(class_id, 0.95)[0]:
            vote_moves += 1
        if class_id != direct_hold:
            direct_hold = class_id
            direct_moves += 1
    check(vote_moves < direct_moves, f"vote {vote_moves} vs direct {direct_moves}")
    return {"frames": len(frames), "vote_moves": vote_moves, "direct_moves": direct_moves}


if __name__ == "__main__":
    test_three_frames_move_once()
    test_low_confidence_resets_streak()
    test_class_change_restarts_vote()
    chatter = test_direct_drive_chatters_more_than_vote()
    print("gesture vote ok", chatter)
