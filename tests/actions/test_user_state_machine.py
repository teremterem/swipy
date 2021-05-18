from typing import Text

import pytest

from actions.user_state_machine import UserStateMachine, UserState

all_expected_states = [
    'new',
    'waiting_partner_answer',
    'ok_for_chitchat',
    'asked_to_join',
    'do_not_disturb',
]


def test_all_expected_states() -> None:
    assert UserState.all == all_expected_states


@pytest.mark.parametrize('source_state', all_expected_states)
def test_request_chitchat(source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
    )
    assert user.user_id == 'some_user_id'
    assert user.state == source_state
    assert user.related_user_id is None
    assert user.newbie is True

    # noinspection PyUnresolvedReferences
    user.request_chitchat('id_of_user_that_was_asked')
    assert user.user_id == 'some_user_id'
    assert user.state == 'waiting_partner_answer'
    assert user.related_user_id == 'id_of_user_that_was_asked'
    assert user.newbie is True
