from typing import Text

import pytest

from actions.user_state_machine import UserStateMachine, UserState


@pytest.mark.parametrize('source_state', [
    'new',
    'wants_chitchat',
    'ok_for_chitchat',
    'do_not_disturb',
])
def test_request_chitchat(source_state: Text) -> None:
    user = UserStateMachine(user_id='some_user_id', state=source_state)
    assert user.state == source_state

    # noinspection PyUnresolvedReferences
    user.request_chitchat()
    assert user.state == UserState.WANTS_CHITCHAT
