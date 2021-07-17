from functools import partial
from typing import Text, Optional
from unittest.mock import Mock, patch

import pytest
from transitions import MachineError

from actions import user_state_machine
from actions.user_state_machine import UserStateMachine, UserState
from tests.tests_common import all_expected_user_states, all_expected_user_state_machine_triggers


def test_all_expected_states() -> None:
    assert list(UserStateMachine('some_user_id').machine.states.keys()) == all_expected_user_states


def test_all_expected_triggers() -> None:
    assert UserStateMachine('some_user_id').machine.get_triggers(*all_expected_user_states) == \
           all_expected_user_state_machine_triggers


expected_catch_all_transitions = [
    ('request_chitchat', 'wants_chitchat', None),
    ('become_ok_to_chitchat', 'ok_to_chitchat', None),
    ('become_do_not_disturb', 'do_not_disturb', None),
    ('wait_for_partner_to_confirm', 'waiting_partner_confirm', 'partner_id_in_trigger'),
    ('become_asked_to_join', 'asked_to_join', 'partner_id_in_trigger'),
    ('become_asked_to_confirm', 'asked_to_confirm', 'partner_id_in_trigger'),
    ('mark_as_bot_blocked', 'bot_blocked', 'previous_partner_id'),
]


@pytest.mark.parametrize('source_state', all_expected_user_states)
@pytest.mark.parametrize('trigger_name, destination_state, expected_partner_id', expected_catch_all_transitions)
def test_catch_all_transitions(
        source_state: Text,
        trigger_name: Text,
        destination_state: Text,
        expected_partner_id: Text,
) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='previous_partner_id',
    )
    assert user.state == source_state
    assert user.partner_id == 'previous_partner_id'

    trigger = partial(getattr(user, trigger_name), 'partner_id_in_trigger')

    if source_state == 'user_banned':
        # transition should fail, no fields should change
        with pytest.raises(MachineError):
            trigger()

        assert user.state == source_state
        assert user.partner_id == 'previous_partner_id'

    else:
        trigger()

        assert user.state == destination_state
        assert user.partner_id == expected_partner_id


expected_more_narrow_transitions = [
    ('join_room', 'new', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'wants_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'ok_to_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'waiting_partner_confirm', 'roomed', 'partner_id_in_trigger', 'partner_id_in_trigger'),
    ('join_room', 'asked_to_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'asked_to_confirm', 'roomed', 'partner_id_in_trigger', 'partner_id_in_trigger'),
    ('join_room', 'roomed', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'rejected_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'rejected_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'do_not_disturb', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'bot_blocked', None, 'previous_partner_id', 'previous_partner_id'),
    ('join_room', 'user_banned', None, 'previous_partner_id', 'previous_partner_id'),

    ('reject', 'new', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'wants_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'ok_to_chitchat', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'waiting_partner_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'asked_to_join', 'rejected_join', 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'asked_to_confirm', 'rejected_confirm', 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'roomed', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'rejected_join', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'rejected_confirm', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'do_not_disturb', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'bot_blocked', None, 'previous_partner_id', 'previous_partner_id'),
    ('reject', 'user_banned', None, 'previous_partner_id', 'previous_partner_id'),
]


def test_expected_more_narrow_transition_list() -> None:
    # make sure we are testing all the transition/initial_state combinations that exist
    assert len({(i[0], i[1]) for i in expected_more_narrow_transitions}) == \
           len(set(all_expected_user_states)) * (len(set(all_expected_user_state_machine_triggers)) -
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
    assert user.roomed_partner_ids == []
    assert user.newbie == initial_newbie_status

    trigger = partial(getattr(user, trigger_name), 'partner_id_in_trigger')

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
        assert user.roomed_partner_ids == [initial_partner_id]
        assert user.newbie is False  # those who joined a room at least once stop being newbies
    else:
        assert user.roomed_partner_ids == []
        assert user.newbie == initial_newbie_status


@pytest.mark.parametrize('source_state', all_expected_user_states)
@pytest.mark.parametrize('trigger_name', all_expected_user_state_machine_triggers)
@pytest.mark.usefixtures('wrap_random_randint')
@patch('time.time', Mock(return_value=1619945501))
def test_state_timestamps(source_state: Text, trigger_name: Text) -> None:
    user = UserStateMachine(
        user_id='some_user_id',
        state=source_state,
        partner_id='some_partner_id',
        state_timestamp=1619697022,
        state_timestamp_str='2021-04-29 11:50:22 Z',
        state_timeout_ts=1619697052,
        state_timeout_ts_str='2021-04-29 11:50:52 Z',
    )
    transition_is_valid = trigger_name in user.machine.get_triggers(source_state)

    trigger = partial(getattr(user, trigger_name), 'some_partner_id')

    if transition_is_valid:
        trigger()  # run trigger and pass partner_id just in case (some triggers need it)

        if user.state in [
            'asked_to_join',
            'asked_to_confirm',
            'rejected_join',
            'rejected_confirm',
        ]:
            expected_timeout_ts = 1619945501 + (60 * 60 * 5)
            expected_timeout_ts_str = '2021-05-02 13:51:41 Z'

        elif user.state == 'waiting_partner_confirm':
            expected_timeout_ts = 1619945501 + 60
            expected_timeout_ts_str = '2021-05-02 08:52:41 Z'

        elif user.state == 'roomed':
            expected_timeout_ts = 1619945501 + (60 * 15)
            expected_timeout_ts_str = '2021-05-02 09:06:41 Z'

        else:
            # destination state is not supposed to have a timeout
            expected_timeout_ts = 0
            expected_timeout_ts_str = None

        assert user == UserStateMachine(
            user_id=user.user_id,  # don't try to validate this
            state=user.state,  # don't try to validate this
            partner_id=user.partner_id,  # don't try to validate this
            roomed_partner_ids=user.roomed_partner_ids,  # don't try to validate this
            rejected_partner_ids=user.rejected_partner_ids,  # don't try to validate this
            seen_partner_ids=user.seen_partner_ids,  # don't try to validate this
            newbie=user.newbie,  # don't try to validate this

            state_timestamp=1619945501,  # new timestamp
            state_timestamp_str='2021-05-02 08:51:41 Z',  # new timestamp
            state_timeout_ts=expected_timeout_ts,
            state_timeout_ts_str=expected_timeout_ts_str,
        )

    else:
        # invalid transition is expected to not go through
        with pytest.raises(MachineError):
            trigger()

        assert user == UserStateMachine(
            user_id=user.user_id,  # don't try to validate this
            state=user.state,  # don't try to validate this
            partner_id=user.partner_id,  # don't try to validate this
            newbie=user.newbie,  # don't try to validate this

            state_timestamp=1619697022,  # timestamp is expected to remain unchanged
            state_timestamp_str='2021-04-29 11:50:22 Z',  # timestamp is expected to remain unchanged
            state_timeout_ts=1619697052,  # timeout timestamp is expected to remain unchanged
            state_timeout_ts_str='2021-04-29 11:50:52 Z',  # timeout timestamp is expected to remain unchanged
        )


@pytest.mark.parametrize('num_of_already_remembered', [
    0,
    1,
    5,
    10,
    15,
])
@pytest.mark.parametrize('num_of_partners_to_remember', [
    0,
    1,
    10,
    None,  # the default
])
@pytest.mark.parametrize('trigger_name, list_name, default_num_var_name, expected_default_num_to_remember', [
    ('join_room', 'roomed_partner_ids', 'NUM_OF_ROOMED_PARTNERS_TO_REMEMBER', 3),
    ('reject', 'rejected_partner_ids', 'NUM_OF_REJECTED_PARTNERS_TO_REMEMBER', 21),
    ('become_asked_to_join', 'seen_partner_ids', 'NUM_OF_SEEN_PARTNERS_TO_REMEMBER', 1),
    ('become_asked_to_confirm', 'seen_partner_ids', 'NUM_OF_SEEN_PARTNERS_TO_REMEMBER', 1),
])
def test_partner_exclusion_lists(
        num_of_already_remembered: int,
        num_of_partners_to_remember: Optional[int],
        trigger_name: Text,
        list_name: Text,
        default_num_var_name: Text,
        expected_default_num_to_remember: int,
):
    user = UserStateMachine(
        user_id='some_user_id',
        state='asked_to_confirm',
        partner_id='partner100500',
    )
    setattr(user, list_name, [f"partner{i}" for i in range(num_of_already_remembered)])

    assert len(getattr(user, list_name)) == num_of_already_remembered

    trigger = partial(getattr(user, trigger_name), 'partner100500')

    if num_of_partners_to_remember is None:
        num_of_partners_to_remember = expected_default_num_to_remember  # the default

        trigger()
    else:
        with patch.object(
                user_state_machine,
                default_num_var_name,
                num_of_partners_to_remember,
        ):
            trigger()

    list_in_question = getattr(user, list_name)

    if num_of_partners_to_remember > 0:
        assert len(list_in_question) == min(num_of_partners_to_remember, num_of_already_remembered + 1)

        if num_of_already_remembered < num_of_partners_to_remember:
            assert list_in_question == [
                f"partner{i}" for i in range(num_of_already_remembered)
            ] + ['partner100500']
        else:
            assert list_in_question == [
                f"partner{i}" for i in range(
                    num_of_already_remembered - num_of_partners_to_remember + 1,
                    num_of_already_remembered,
                )
            ] + ['partner100500']
    else:
        assert list_in_question == []
