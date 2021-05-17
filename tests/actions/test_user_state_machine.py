from actions.user_state_machine import UserStateMachine


def test_request_chitchat(user1: UserStateMachine) -> None:
    assert user1.state == UserStateMachine.STATE_OK_FOR_CHITCHAT
    # noinspection PyUnresolvedReferences
    user1.request_chitchat()
    assert user1.state == UserStateMachine.STATE_WANTS_CHITCHAT
