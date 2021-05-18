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
def test_ask_partner(source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
    )
    partner = UserStateMachine(
        user_id='some_partner_id',
        state=UserState.OK_FOR_CHITCHAT,
    )

    assert user.state == source_state
    assert user.related_user_id is None

    assert partner.state == UserState.OK_FOR_CHITCHAT
    assert partner.related_user_id is None

    # noinspection PyUnresolvedReferences
    user.ask_partner(partner)

    assert user.state == 'waiting_partner_answer'
    assert user.related_user_id == 'some_partner_id'

    assert partner.state == UserState.ASKED_TO_JOIN
    assert partner.related_user_id == 'some_user_id'
