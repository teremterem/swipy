from datetime import datetime
from typing import Text
from unittest.mock import Mock, patch

import pytest
from transitions import MachineError

from actions.user_state_machine import UserStateMachine, UserState

all_expected_states = [
    'new',
    'waiting_partner_answer',
    'ok_to_chitchat',
    'asked_to_join',
    'do_not_disturb',
]

all_expected_triggers = [
    'ask_partner',
    'become_ok_to_chitchat',
    'become_asked_to_join',
    'join_room',
    'become_do_not_disturb',
]


def test_all_expected_states() -> None:
    assert list(UserStateMachine('some_user_id').machine.states.keys()) == all_expected_states


def test_all_expected_triggers() -> None:
    assert list(UserStateMachine('some_user_id').machine.get_triggers(*all_expected_states)) == all_expected_triggers


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
        state=UserState.OK_TO_CHITCHAT,
    )
    assert user.state == 'ok_to_chitchat'
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
def test_become_ok_to_chitchat(source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='previous_partner_id',
    )

    assert user.state == source_state
    assert user.partner_id == 'previous_partner_id'

    # noinspection PyUnresolvedReferences
    user.become_ok_to_chitchat()

    assert user.state == 'ok_to_chitchat'
    assert user.partner_id is None


@pytest.mark.parametrize('source_state', [
    'waiting_partner_answer',
    'asked_to_join',
])
@pytest.mark.parametrize('newbie_status', [True, False])
def test_join_room(source_state: Text, newbie_status: bool) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='asker_id',
        newbie=newbie_status,
    )

    assert user.state == source_state
    assert user.partner_id == 'asker_id'
    assert user.newbie == newbie_status

    # noinspection PyUnresolvedReferences
    user.join_room()

    assert user.state == 'ok_to_chitchat'
    assert user.partner_id is None
    assert user.newbie is False  # users stop being newbies as soon as they accept their first video chitchat


@pytest.mark.parametrize('invalid_source_state', [
    'new',
    'ok_to_chitchat',
    'do_not_disturb',
])
def test_join_room_wrong_state(invalid_source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=invalid_source_state,
        partner_id='some_unrelated_partner_id',
        newbie=True,
    )

    assert user.state == invalid_source_state
    assert user.partner_id == 'some_unrelated_partner_id'
    assert user.newbie is True

    with pytest.raises(MachineError):
        # noinspection PyUnresolvedReferences
        user.join_room()

    assert user.state == invalid_source_state
    assert user.partner_id == 'some_unrelated_partner_id'
    assert user.newbie is True


@pytest.mark.parametrize('source_state', all_expected_states)
@pytest.mark.parametrize('newbie_status', [True, False])
def test_become_do_not_disturb(source_state: Text, newbie_status: bool) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='asker_id',
        newbie=newbie_status,
    )

    assert user.state == source_state
    assert user.partner_id == 'asker_id'
    assert user.newbie == newbie_status

    # noinspection PyUnresolvedReferences
    user.become_do_not_disturb()

    assert user.state == 'do_not_disturb'
    assert user.partner_id is None
    assert user.newbie == newbie_status


@patch('time.time', Mock(return_value=1619945501))
@pytest.mark.parametrize('source_state', all_expected_states)
@pytest.mark.parametrize('trigger_name', all_expected_triggers)
def test_state_timestamp(source_state: Text, trigger_name: Text) -> None:
    source_state_timestamp = 1619697022
    source_state_timestamp_str = datetime.utcfromtimestamp(source_state_timestamp).strftime('%Y-%m-%d %H:%M:%S Z')

    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='asker_id',
        newbie=False,
        state_timestamp=source_state_timestamp,
        state_timestamp_str=source_state_timestamp_str,
    )
    expect_timestamp_to_change = trigger_name in user.machine.get_triggers(source_state)

    assert user.state_timestamp == 1619697022
    assert user.state_timestamp_str == '2021-04-29 11:50:22 Z'

    trigger = getattr(user, trigger_name)

    if expect_timestamp_to_change:
        trigger(partner_id='some_partner_id')  # run trigger and pass partner_id just in case (some triggers need it)

        assert user.state_timestamp == 1619945501
        assert user.state_timestamp_str == '2021-05-02 08:51:41 Z'
    else:
        with pytest.raises(MachineError):
            trigger(partner_id='some_partner_id')

        assert user.state_timestamp == 1619697022  # same timestamp as before
        assert user.state_timestamp_str == '2021-04-29 11:50:22 Z'  # same timestamp as before
