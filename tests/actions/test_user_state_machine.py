from datetime import datetime
from functools import partial
from typing import Text, Optional
from unittest.mock import Mock, patch

import pytest
from transitions import MachineError

from actions.user_state_machine import UserStateMachine

all_expected_states = [
    'new',
    'wants_chitchat',
    'ok_to_chitchat',
    'waiting_partner_join',
    'waiting_partner_confirm',
    'asked_to_join',
    'asked_to_confirm',
    'roomed',
    'rejected_join',
    'rejected_confirm',
    'join_timed_out',
    'confirm_timed_out',
    'do_not_disturb',
]

all_expected_triggers = [
    'request_chitchat',
    'become_ok_to_chitchat',
    'become_do_not_disturb',
    'wait_for_partner',
    'become_asked',
    'join_room',
    'reject',
    'time_out',
]


def test_all_expected_states() -> None:
    assert list(UserStateMachine('some_user_id').machine.states.keys()) == all_expected_states


def test_all_expected_triggers() -> None:
    assert UserStateMachine('some_user_id').machine.get_triggers(*all_expected_states) == all_expected_triggers


@pytest.mark.parametrize('source_state', all_expected_states)
@pytest.mark.parametrize('trigger_name, destination_state', [
    ('request_chitchat', 'wants_chitchat'),
    ('become_ok_to_chitchat', 'ok_to_chitchat'),
    ('become_do_not_disturb', 'do_not_disturb'),
])
def test_catch_all_transitions(
        source_state: Text,
        trigger_name: Text,
        destination_state: Text,
) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='previous_partner_id',
    )
    assert user.state == source_state
    assert user.partner_id == 'previous_partner_id'

    trigger = getattr(user, trigger_name)
    trigger('new_partner_id')  # this parameter is expected to be ignored

    assert user.state == destination_state
    assert user.partner_id is None  # previous partner is expected to be dropped


@pytest.mark.parametrize('source_state, trigger_name, destination_state, partner_should_be_updated', [
    ('new', 'wait_for_partner', None, None),
    ('wants_chitchat', 'wait_for_partner', 'waiting_partner_join', True),
    ('ok_to_chitchat', 'wait_for_partner', None, None),
    ('waiting_partner_join', 'wait_for_partner', None, None),
    ('waiting_partner_confirm', 'wait_for_partner', None, None),
    ('asked_to_join', 'wait_for_partner', 'waiting_partner_confirm', None),
    ('asked_to_confirm', 'wait_for_partner', None, None),
    ('roomed', 'wait_for_partner', None, None),
    ('rejected_join', 'wait_for_partner', None, None),
    ('rejected_confirm', 'wait_for_partner', None, None),
    ('join_timed_out', 'wait_for_partner', None, None),
    ('confirm_timed_out', 'wait_for_partner', None, None),
    ('do_not_disturb', 'wait_for_partner', None, None),

    ('new', 'become_asked', None, None),
    ('wants_chitchat', 'become_asked', 'asked_to_join', True),
    ('ok_to_chitchat', 'become_asked', 'asked_to_join', True),
    ('waiting_partner_join', 'become_asked', 'asked_to_confirm', False),
    ('waiting_partner_confirm', 'become_asked', None, None),
    ('asked_to_join', 'become_asked', None, None),
    ('asked_to_confirm', 'become_asked', None, None),
    ('roomed', 'become_asked', 'asked_to_join', True),
    ('rejected_join', 'become_asked', 'asked_to_join', True),
    ('rejected_confirm', 'become_asked', 'asked_to_join', True),
    ('join_timed_out', 'become_asked', 'asked_to_join', True),
    ('confirm_timed_out', 'become_asked', 'asked_to_join', True),
    ('do_not_disturb', 'become_asked', None, None),
])
def test_transitions_that_involve_partner(
        source_state: Text,
        trigger_name: Text,
        destination_state: Optional[Text],
        partner_should_be_updated: Optional[bool],
) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='previous_partner_id',
    )
    assert user.state == source_state
    assert user.partner_id == 'previous_partner_id'

    trigger = partial(getattr(user, trigger_name), 'new_partner_id')

    if destination_state:
        trigger()

        assert user.state == destination_state

    else:
        # transition is expected to be invalid
        with pytest.raises(MachineError):
            trigger()

        assert user.state == source_state  # state is expected to not be changed

    if partner_should_be_updated:
        assert user.partner_id == 'new_partner_id'
    else:
        assert user.partner_id == 'previous_partner_id'


# TODO TODO TODO
# TODO TODO TODO
# TODO TODO TODO


@pytest.mark.parametrize('source_state', all_expected_states)
def test_wait_for_partner(source_state: Text) -> None:
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


@pytest.mark.parametrize('source_state', [
    'ok_to_chitchat',
    'waiting_partner_answer',
])
def test_become_asked_to_join(source_state: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
    )
    assert user.state == source_state
    assert user.partner_id is None

    # noinspection PyUnresolvedReferences
    user.become_asked_to_join('asker_id')

    assert user.state == 'asked_to_join'
    assert user.partner_id == 'asker_id'


@pytest.mark.parametrize('wrong_state', [
    'new',
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
    transition_is_valid = trigger_name in user.machine.get_triggers(source_state)

    assert user.state_timestamp == 1619697022
    assert user.state_timestamp_str == '2021-04-29 11:50:22 Z'

    trigger = getattr(user, trigger_name)

    transitions_that_dont_change_state = [
        ('waiting_partner_answer', 'ask_partner'),
        ('ok_to_chitchat', 'become_ok_to_chitchat'),
        ('do_not_disturb', 'become_do_not_disturb'),
    ]

    if (source_state, trigger_name) in transitions_that_dont_change_state:
        # transition is valid but it leads to the same state as before => timestamp should not be changed
        trigger('some_partner_id')

        assert user.state_timestamp == 1619697022  # timestamp is expected to remain unchanged
        assert user.state_timestamp_str == '2021-04-29 11:50:22 Z'  # timestamp is expected to remain unchanged

    elif transition_is_valid:
        trigger('some_partner_id')  # run trigger and pass partner_id just in case (some triggers need it)

        assert user.state_timestamp == 1619945501  # new timestamp
        assert user.state_timestamp_str == '2021-05-02 08:51:41 Z'  # new timestamp

    else:
        # invalid transition is expected to not go through
        with pytest.raises(MachineError):
            trigger(partner_id='some_partner_id')

        assert user.state_timestamp == 1619697022  # timestamp is expected to remain unchanged
        assert user.state_timestamp_str == '2021-04-29 11:50:22 Z'  # timestamp is expected to remain unchanged
