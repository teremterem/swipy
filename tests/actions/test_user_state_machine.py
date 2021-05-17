from typing import Text

import pytest

from actions.user_state_machine import UserStateMachine


@pytest.mark.parametrize('source_state', [
    'new',
    'wants_chitchat',
    'ok_for_chitchat',
    'do_not_disturb',
])
def test_request_chitchat(source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        related_user_id='test_related_user_id',
    )
    assert user.user_id == 'some_user_id'
    assert user.state == source_state
    assert user.related_user_id == 'test_related_user_id'

    # noinspection PyUnresolvedReferences
    user.request_chitchat()
    assert user.user_id == 'some_user_id'
    assert user.state == 'wants_chitchat'
    assert user.related_user_id is None  # when user requests chitchat we clear whatever previous partner they may had
