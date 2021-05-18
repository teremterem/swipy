from typing import Text

import pytest

from actions.user_state_machine import UserStateMachine, UserState

all_expected_states = [
    'new',
    'waiting_partner_answer',
    'ok_for_chitchat_newbie',
    'ok_for_chitchat_veteran',
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
        related_user_id='test_related_user_id',
    )
    assert user.user_id == 'some_user_id'
    assert user.state == source_state
    assert user.related_user_id == 'test_related_user_id'

    # noinspection PyUnresolvedReferences
    user.request_chitchat()
    assert user.user_id == 'some_user_id'
    assert user.state == 'waiting_partner_answer'
    assert user.related_user_id is None  # when user requests chitchat we clear whatever previous partner they may had
