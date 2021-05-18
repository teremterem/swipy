from typing import Text

import pytest
from transitions import MachineError

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

    assert partner.state == 'ok_for_chitchat'
    assert partner.related_user_id is None

    # noinspection PyUnresolvedReferences
    user.ask_partner(partner)

    assert user.state == 'waiting_partner_answer'
    assert user.related_user_id == 'some_partner_id'

    assert partner.state == 'asked_to_join'
    assert partner.related_user_id == 'some_user_id'


@pytest.mark.parametrize('wrong_partner_state', [
    'new',
    'waiting_partner_answer',
    'asked_to_join',
    'do_not_disturb',
])
def test_ask_wrong_partner(wrong_partner_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=UserState.NEW,
    )
    partner = UserStateMachine(
        user_id='some_partner_id',
        state=wrong_partner_state,
        related_user_id='some_unrelated_user_id',
    )

    assert user.state == 'new'
    assert user.related_user_id is None

    assert partner.state == wrong_partner_state
    assert partner.related_user_id == 'some_unrelated_user_id'

    with pytest.raises(MachineError):
        # noinspection PyUnresolvedReferences
        user.ask_partner(partner)

    assert user.state == 'new'
    assert user.related_user_id is None

    assert partner.state == wrong_partner_state
    assert partner.related_user_id == 'some_unrelated_user_id'
