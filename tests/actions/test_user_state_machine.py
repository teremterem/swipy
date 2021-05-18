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
    assert user.state == source_state
    assert user.partner_id is None

    # noinspection PyUnresolvedReferences
    user.ask_partner('some_partner_id')

    assert user.state == 'waiting_partner_answer'
    assert user.partner_id == 'some_partner_id'


def test_become_asked_to_join() -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=UserState.OK_FOR_CHITCHAT,
    )
    assert user.state == 'ok_for_chitchat'
    assert user.partner_id is None

    # noinspection PyUnresolvedReferences
    user.become_asked_to_join('asker_id')

    assert user.state == 'asked_to_join'
    assert user.partner_id == 'asker_id'


@pytest.mark.parametrize('wrong_state', [
    'new',
    'waiting_partner_answer',
    'asked_to_join',
    'do_not_disturb',
])
def test_become_asked_to_join_wrong_state(wrong_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=wrong_state,
        partner_id='some_unrelated_partner_id',
    )

    assert user.state == wrong_state
    assert user.partner_id == 'some_unrelated_partner_id'

    with pytest.raises(MachineError):
        # noinspection PyUnresolvedReferences
        user.become_asked_to_join('asker_id')

    assert user.state == wrong_state
    assert user.partner_id == 'some_unrelated_partner_id'


@pytest.mark.parametrize('source_state', all_expected_states)
def test_fail_to_find_partner(source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='previous_partner_id',
    )

    assert user.state == source_state
    assert user.partner_id == 'previous_partner_id'

    # noinspection PyUnresolvedReferences
    user.fail_to_find_partner()

    assert user.state == 'ok_for_chitchat'
    assert user.partner_id is None


@pytest.mark.parametrize('source_state', all_expected_states)
def test_become_ok_for_chitchat(source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='previous_partner_id',
    )

    assert user.state == source_state
    assert user.partner_id == 'previous_partner_id'

    # noinspection PyUnresolvedReferences
    user.become_ok_for_chitchat()

    assert user.state == 'ok_for_chitchat'
    assert user.partner_id is None


@pytest.mark.parametrize('newbie_status', [True, False])
def test_accept_invitation(newbie_status) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=UserState.ASKED_TO_JOIN,
        partner_id='asker_id',
        newbie=newbie_status,
    )

    assert user.state == 'asked_to_join'
    assert user.partner_id == 'asker_id'
    assert user.newbie == newbie_status

    # noinspection PyUnresolvedReferences
    user.accept_invitation()

    assert user.state == 'ok_for_chitchat'
    assert user.partner_id == 'asker_id'
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
        partner_id='some_unrelated_partner_id',
        newbie=True,
    )

    assert user.state == wrong_state
    assert user.partner_id == 'some_unrelated_partner_id'
    assert user.newbie is True

    with pytest.raises(MachineError):
        # noinspection PyUnresolvedReferences
        user.accept_invitation()

    assert user.state == wrong_state
    assert user.partner_id == 'some_unrelated_partner_id'
    assert user.newbie is True


@pytest.mark.parametrize('newbie_status', [True, False])
def test_reject_invitation(newbie_status) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=UserState.ASKED_TO_JOIN,
        partner_id='asker_id',
        newbie=newbie_status,
    )

    assert user.state == 'asked_to_join'
    assert user.partner_id == 'asker_id'
    assert user.newbie == newbie_status

    # noinspection PyUnresolvedReferences
    user.reject_invitation()

    assert user.state == 'do_not_disturb'
    assert user.partner_id is None
    assert user.newbie == newbie_status


@pytest.mark.parametrize('wrong_state', [
    'new',
    'waiting_partner_answer',
    'ok_for_chitchat',
    'do_not_disturb',
])
def test_reject_invitation_wrong_state(wrong_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=wrong_state,
        partner_id='some_unrelated_partner_id',
        newbie=True,
    )

    assert user.state == wrong_state
    assert user.partner_id == 'some_unrelated_partner_id'
    assert user.newbie is True

    with pytest.raises(MachineError):
        # noinspection PyUnresolvedReferences
        user.reject_invitation()

    assert user.state == wrong_state
    assert user.partner_id == 'some_unrelated_partner_id'
    assert user.newbie is True
