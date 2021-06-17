from datetime import datetime
from functools import partial
from typing import Text, Optional
from unittest.mock import Mock, patch

import pytest
from transitions import MachineError

from actions.user_state_machine import UserStateMachine, UserState

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


expected_catch_all_transitions = [
    ('request_chitchat', 'wants_chitchat'),
    ('become_ok_to_chitchat', 'ok_to_chitchat'),
    ('become_do_not_disturb', 'do_not_disturb'),
]


@pytest.mark.parametrize('source_state', all_expected_states)
@pytest.mark.parametrize('trigger_name, destination_state', expected_catch_all_transitions)
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


expected_more_narrow_transitions = [
    ('wait_for_partner', 'new', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'wants_chitchat', 'waiting_partner_join', 'previous_partner_id', 'new_partner_id'),
    ('wait_for_partner', 'ok_to_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'waiting_partner_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'waiting_partner_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'asked_to_join', 'waiting_partner_confirm', 'new_partner_id', 'new_partner_id'),
    ('wait_for_partner', 'asked_to_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'roomed', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'rejected_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'rejected_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'join_timed_out', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'confirm_timed_out', None, 'previous_partner_id', 'previous_partner_id'),
    ('wait_for_partner', 'do_not_disturb', None, 'previous_partner_id', 'previous_partner_id'),

    ('become_asked', 'new', None, 'previous_partner_id', 'previous_partner_id'),
    ('become_asked', 'wants_chitchat', 'asked_to_join', 'previous_partner_id', 'new_partner_id'),
    ('become_asked', 'ok_to_chitchat', 'asked_to_join', 'previous_partner_id', 'new_partner_id'),
    ('become_asked', 'waiting_partner_join', 'asked_to_confirm', 'new_partner_id', 'new_partner_id'),
    ('become_asked', 'waiting_partner_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('become_asked', 'asked_to_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('become_asked', 'asked_to_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('become_asked', 'roomed', 'asked_to_join', 'previous_partner_id', 'new_partner_id'),
    ('become_asked', 'rejected_join', None, 'previous_partner_id', 'previous_partner_id'),  # TODO oleksandr
    ('become_asked', 'rejected_confirm', None, 'previous_partner_id', 'previous_partner_id'),  # TODO oleksandr
    ('become_asked', 'join_timed_out', None, 'previous_partner_id', 'previous_partner_id'),
    ('become_asked', 'confirm_timed_out', None, 'previous_partner_id', 'previous_partner_id'),
    ('become_asked', 'do_not_disturb', None, 'previous_partner_id', 'previous_partner_id'),

    ('join_room', 'new', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'wants_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'ok_to_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'waiting_partner_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'waiting_partner_confirm', 'roomed', 'new_partner_id', 'new_partner_id'),
    ('join_room', 'asked_to_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'asked_to_confirm', 'roomed', 'new_partner_id', 'new_partner_id'),
    ('join_room', 'roomed', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'rejected_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'rejected_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'join_timed_out', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'confirm_timed_out', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'do_not_disturb', None, 'previous_partner_id', 'previous_partner_id'),

    ('reject', 'new', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'wants_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'ok_to_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'waiting_partner_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'waiting_partner_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'asked_to_join', 'rejected_join', 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'asked_to_confirm', 'rejected_confirm', 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'roomed', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'rejected_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'rejected_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'join_timed_out', 'rejected_join', 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'confirm_timed_out', 'rejected_confirm', 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'do_not_disturb', None, 'previous_partner_id', 'previous_partner_id'),

    ('time_out', 'new', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'wants_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'ok_to_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'waiting_partner_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'waiting_partner_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'asked_to_join', 'join_timed_out', 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'asked_to_confirm', 'confirm_timed_out', 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'roomed', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'rejected_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'rejected_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'join_timed_out', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'confirm_timed_out', None, 'previous_partner_id', 'previous_partner_id'),
    ('time_out', 'do_not_disturb', None, 'previous_partner_id', 'previous_partner_id'),
]


def test_expected_more_narrow_transition_list() -> None:
    # make sure we are testing all the transition/initial_state combinations that exist
    assert len({(i[0], i[1]) for i in expected_more_narrow_transitions}) == \
           len(set(all_expected_states)) * (len(set(all_expected_triggers)) -
                                            len({i[0] for i in expected_catch_all_transitions}))


@pytest.mark.parametrize('initial_newbie_status', [True, False])
@pytest.mark.parametrize(
    'trigger_name, source_state, destination_state, initial_partner_id, expected_partner_id',
    expected_more_narrow_transitions,
)
def test_more_narrow_transitions(
        initial_newbie_status: bool,
        source_state: Text,
        trigger_name: Text,
        destination_state: Optional[Text],
        initial_partner_id: Optional[Text],
        expected_partner_id: Optional[Text],
) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id=initial_partner_id,
        newbie=initial_newbie_status,
    )
    assert user.state == source_state
    assert user.partner_id == initial_partner_id

    trigger = partial(getattr(user, trigger_name), 'new_partner_id')

    if destination_state:
        trigger()

        assert user.state == destination_state

    else:
        # transition is expected to be invalid
        with pytest.raises(MachineError):
            trigger()

        assert user.state == source_state  # state is expected to not be changed

    assert user.partner_id == expected_partner_id

    if destination_state == UserState.ROOMED:
        # those who joined a room at least once stop being newbies
        assert user.newbie is False
    else:
        assert user.newbie == initial_newbie_status


@patch('time.time', Mock(return_value=1619945501))
@pytest.mark.parametrize('source_state', all_expected_states)
@pytest.mark.parametrize('trigger_name', all_expected_triggers)
def test_state_timestamp(source_state: Text, trigger_name: Text) -> None:
    source_state_timestamp = 1619697022
    source_state_timestamp_str = datetime.utcfromtimestamp(source_state_timestamp).strftime('%Y-%m-%d %H:%M:%S Z')

    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='some_partner_id',
        state_timestamp=source_state_timestamp,
        state_timestamp_str=source_state_timestamp_str,
    )
    transition_is_valid = trigger_name in user.machine.get_triggers(source_state)

    assert user.state_timestamp == 1619697022
    assert user.state_timestamp_str == '2021-04-29 11:50:22 Z'

    trigger = getattr(user, trigger_name)

    if transition_is_valid:
        trigger('some_partner_id')  # run trigger and pass partner_id just in case (some triggers need it)

        assert user.state_timestamp == 1619945501  # new timestamp
        assert user.state_timestamp_str == '2021-05-02 08:51:41 Z'  # new timestamp

    else:
        # invalid transition is expected to not go through
        with pytest.raises(MachineError):
            trigger(partner_id='some_partner_id')

        assert user.state_timestamp == 1619697022  # timestamp is expected to remain unchanged
        assert user.state_timestamp_str == '2021-04-29 11:50:22 Z'  # timestamp is expected to remain unchanged
