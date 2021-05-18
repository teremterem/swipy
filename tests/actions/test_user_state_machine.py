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
def test_ask_partner_wrong_partner_state(wrong_partner_state: Text) -> None:
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


@pytest.mark.parametrize('source_state', all_expected_states)
def test_fail_to_find_partner(source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        related_user_id='previous_related_user_id',
    )

    assert user.state == source_state
    assert user.related_user_id == 'previous_related_user_id'

    # noinspection PyUnresolvedReferences
    user.fail_to_find_partner()

    assert user.state == 'ok_for_chitchat'
    assert user.related_user_id is None


@pytest.mark.parametrize('source_state', all_expected_states)
def test_become_ok_for_chitchat(source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        related_user_id='previous_related_user_id',
    )

    assert user.state == source_state
    assert user.related_user_id == 'previous_related_user_id'

    # noinspection PyUnresolvedReferences
    user.become_ok_for_chitchat()

    assert user.state == 'ok_for_chitchat'
    assert user.related_user_id is None


@pytest.mark.parametrize('newbie_status', [True, False])
def test_accept_invitation(newbie_status) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=UserState.ASKED_TO_JOIN,
        related_user_id='asker_id',
        newbie=newbie_status,
    )

    assert user.state == 'asked_to_join'
    assert user.related_user_id == 'asker_id'
    assert user.newbie == newbie_status

    # noinspection PyUnresolvedReferences
    user.accept_invitation()

    assert user.state == 'ok_for_chitchat'
    assert user.related_user_id == 'asker_id'  # TODO oleksandr: are you sure this makes sense ?
    assert user.newbie is False  # users stop being newbies as soon as they accept their first video chitchat


@pytest.mark.parametrize('wrong_state', [
    'new',
    'waiting_partner_answer',
    'ok_for_chitchat',
    'do_not_disturb',
])
def test_accept_invitation_wrong_state(wrong_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=wrong_state,
        related_user_id='some_unrelated_user_id',
        newbie=True,
    )

    assert user.state == wrong_state
    assert user.related_user_id == 'some_unrelated_user_id'
    assert user.newbie is True

    with pytest.raises(MachineError):
        # noinspection PyUnresolvedReferences
        user.accept_invitation()

    assert user.state == wrong_state
    assert user.related_user_id == 'some_unrelated_user_id'
    assert user.newbie is True
