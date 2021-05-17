from actions.user_state_machine import UserStateMachine, UserState


def test_request_chitchat(user1: UserStateMachine) -> None:
    assert user1.state == UserState.OK_FOR_CHITCHAT
    # noinspection PyUnresolvedReferences
    user1.request_chitchat()
    assert user1.state == UserState.WANTS_CHITCHAT
