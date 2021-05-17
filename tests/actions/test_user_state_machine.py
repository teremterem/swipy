from actions.user_state_machine import UserStateMachine, UserState


def test_request_chitchat(ddb_user1: UserStateMachine) -> None:
    assert ddb_user1.state == UserState.OK_FOR_CHITCHAT
    # noinspection PyUnresolvedReferences
    ddb_user1.request_chitchat()
    assert ddb_user1.state == UserState.WANTS_CHITCHAT
