import traceback
from dataclasses import asdict
from typing import Dict, Text, Any, List, Callable, Tuple
from unittest.mock import patch, AsyncMock, MagicMock, call, Mock

import pytest
from aioresponses import aioresponses, CallbackResult
from rasa_sdk import Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType
from rasa_sdk.executor import CollectingDispatcher

from actions import actions, daily_co
from actions.user_state_machine import UserStateMachine, UserState
from actions.user_vault import UserVault, IUserVault


@pytest.mark.asyncio
@patch.object(UserVault, '_get_user')
async def test_user_vault_cache_not_reused_between_action_runs(
        mock_ddb_get_user: MagicMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        unit_test_user: UserStateMachine,
) -> None:
    mock_ddb_get_user.return_value = unit_test_user

    class SomeSwiperAction(actions.BaseSwiperAction):
        def name(self) -> Text:
            return 'some_swiper_action'

        async def swipy_run(
                self, _dispatcher: CollectingDispatcher,
                _tracker: Tracker,
                _domain: Dict[Text, Any],
                _current_user: UserStateMachine,
                _user_vault: IUserVault,
        ) -> List[Dict[Text, Any]]:
            _user_vault.get_user('unit_test_user')
            _user_vault.get_user('unit_test_user')
            _user_vault.get_user(_tracker.sender_id)  # which is also 'unit_test_user'
            _user_vault.get_user(_tracker.sender_id)  # which is also 'unit_test_user'
            return []

    action = SomeSwiperAction()

    await action.run(dispatcher, tracker, domain)
    assert mock_ddb_get_user.mock_calls == [
        call('unit_test_user'),
    ]

    await action.run(dispatcher, tracker, domain)
    assert mock_ddb_get_user.mock_calls == [
        call('unit_test_user'),
        call('unit_test_user'),  # new run should use new cache
    ]


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
async def test_swiper_state_and_partner_id_slots_are_set_after_action_run(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    class SomeSwiperAction(actions.BaseSwiperAction):
        def name(self) -> Text:
            return 'some_swiper_action'

        async def swipy_run(
                self, _dispatcher: CollectingDispatcher,
                _tracker: Tracker,
                _domain: Dict[Text, Any],
                _current_user: UserStateMachine,
                _user_vault: IUserVault,
        ) -> List[Dict[Text, Any]]:
            assert _current_user.user_id == 'unit_test_user'
            assert _current_user.state == 'new'
            assert _current_user.partner_id is None

            _user_vault.save(UserStateMachine(
                user_id=_current_user.user_id,
                state=UserState.OK_TO_CHITCHAT,
                partner_id='some_partner_id',
            ))  # save a completely different instance of the current user
            return []

    action = SomeSwiperAction()

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),  # the action is expected to use the most recent value of state
        SlotSet('partner_id', 'some_partner_id'),  # the action is expected to use the most recent value of partner_id
    ]
    assert dispatcher.messages == []


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
async def test_action_session_start_without_slots(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    action = actions.ActionSessionStart()
    assert action.name() == 'action_session_start'

    tracker.slots.clear()
    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SessionStarted(),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'new'),  # state taken from UserVault
        SlotSet('partner_id', None),  # partner_id taken from UserVault
        ActionExecuted('action_listen'),
    ]
    assert dispatcher.messages == []


@pytest.mark.asyncio
@pytest.mark.parametrize('carry_over_slots_to_new_session, expected_events', [
    (
            True,
            [
                SessionStarted(),
                SlotSet('session_started_metadata', None),  # comes from tests/actions/data/initial_tracker.json
                SlotSet('room_url', None),  # comes from tests/actions/data/initial_tracker.json
                SlotSet('my_slot', 'value'),
                SlotSet('another-slot', 'value2'),
                # two more events (swiper_state slot and action_listen) are appended inside the test itself
            ],
    ),
    (
            False,
            [
                SessionStarted(),
                # two more events (swiper_state slot and action_listen) are appended inside the test itself
            ],
    ),
])
@pytest.mark.usefixtures('create_user_state_machine_table')
async def test_action_session_start_with_slots(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        carry_over_slots_to_new_session: bool,
        expected_events: List[EventType],
) -> None:
    from actions.aws_resources import user_state_machine_table
    # noinspection PyDataclass
    user_state_machine_table.put_item(Item=asdict(UserStateMachine(
        user_id='unit_test_user',
        state=UserState.OK_TO_CHITCHAT,
    )))

    # set a few slots on tracker
    tracker.add_slots([
        SlotSet('my_slot', 'value'),
        SlotSet('swiper_state', 'do_not_disturb'),  # expected to be replaced rather than carried over
        SlotSet('partner_id', 'some_old_partner'),  # expected to be replaced rather than carried over
        SlotSet('another-slot', 'value2'),
    ])

    domain['session_config']['carry_over_slots_to_new_session'] = carry_over_slots_to_new_session
    expected_events = expected_events + [
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),  # state taken from UserVault rather than carried over
        SlotSet('partner_id', None),  # partner_id taken from UserVault rather than carried over
        ActionExecuted(action_name='action_listen'),
    ]

    assert await actions.ActionSessionStart().run(dispatcher, tracker, domain) == expected_events
    assert dispatcher.messages == []


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('time.time', Mock(return_value=1619945501))
@patch.object(UserVault, '_list_available_user_dicts')
@patch('asyncio.sleep')
async def test_action_find_partner_newbie(
        mock_asyncio_sleep: AsyncMock,
        mock_list_available_user_dicts: MagicMock,
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        available_newbie1: UserStateMachine,
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
        external_intent_response: Dict[Text, Any],
) -> None:
    # noinspection PyDataclass
    mock_list_available_user_dicts.return_value = [asdict(available_newbie1)]

    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'available_newbie_id1',
        'EXTERNAL_ask_to_join',
        {
            'partner_id': 'unit_test_user',
        },
    )
    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=external_intent_response))
    mock_aioresponses.post(expected_rasa_url, callback=mock_rasa_callbacks)

    action = actions.ActionFindPartner()
    assert action.name() == 'action_find_partner'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_has_been_asked'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'waiting_partner_answer'),
        SlotSet('partner_id', 'available_newbie_id1'),
    ]
    assert dispatcher.messages == []

    mock_asyncio_sleep.assert_called_once_with(1.1)
    mock_list_available_user_dicts.assert_called_once_with(exclude_user_id='unit_test_user', newbie=True)
    assert mock_rasa_callbacks.mock_calls == [expected_rasa_call]

    user_vault = UserVault()
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='waiting_partner_answer',
        partner_id='available_newbie_id1',
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('time.time', Mock(return_value=1619945501))
@patch.object(UserVault, '_list_available_user_dicts')
@patch('asyncio.sleep')
async def test_action_find_partner_veteran(
        mock_asyncio_sleep: AsyncMock,
        mock_list_available_user_dicts: MagicMock,
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        available_veteran1: UserStateMachine,
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
        external_intent_response: Dict[Text, Any],
) -> None:
    # noinspection PyDataclass
    mock_list_available_user_dicts.side_effect = [
        [],  # first call - no newbies
        [asdict(available_veteran1)],  # second call - one veteran
    ]

    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'available_veteran_id1',
        'EXTERNAL_ask_to_join',
        {
            'partner_id': 'unit_test_user',
        },
    )
    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=external_intent_response))
    mock_aioresponses.post(expected_rasa_url, callback=mock_rasa_callbacks)

    actual_events = await actions.ActionFindPartner().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_has_been_asked'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'waiting_partner_answer'),
        SlotSet('partner_id', 'available_veteran_id1'),
    ]
    assert dispatcher.messages == []

    mock_asyncio_sleep.assert_called_once_with(1.1)
    assert mock_list_available_user_dicts.mock_calls == [
        call(exclude_user_id='unit_test_user', newbie=True),
        call(exclude_user_id='unit_test_user', newbie=False),
    ]
    assert mock_rasa_callbacks.mock_calls == [expected_rasa_call]

    user_vault = UserVault()
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='waiting_partner_answer',
        partner_id='available_veteran_id1',
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('time.time', Mock(return_value=1619945501))
@patch('actions.rasa_callbacks.ask_to_join')
@patch.object(UserVault, '_list_available_user_dicts')
@patch('asyncio.sleep')
async def test_action_find_partner_no_one(
        mock_asyncio_sleep: AsyncMock,
        mock_list_available_user_dicts: MagicMock,
        mock_rasa_callback_ask_to_join: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    mock_list_available_user_dicts.side_effect = [
        [],  # first call - no newbies
        [],  # second call - no veterans
    ]

    actual_events = await actions.ActionFindPartner().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_was_not_found'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),
        SlotSet('partner_id', None),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_no_one_was_found',
        'template': 'utter_no_one_was_found',
        'text': None,
    }]

    mock_asyncio_sleep.assert_called_once_with(1.1)
    assert mock_list_available_user_dicts.mock_calls == [
        call(exclude_user_id='unit_test_user', newbie=True),
        call(exclude_user_id='unit_test_user', newbie=False),
    ]
    mock_rasa_callback_ask_to_join.assert_not_called()

    user_vault = UserVault()
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='ok_to_chitchat',
        partner_id=None,
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('time.time', Mock(return_value=1619945501))
@patch('actions.rasa_callbacks.ask_to_join')
@patch.object(UserVault, '_list_available_user_dicts')
@patch('asyncio.sleep')
async def test_action_find_partner_swiper_error_trace(
        mock_asyncio_sleep: AsyncMock,
        mock_list_available_user_dicts: MagicMock,
        mock_rasa_callback_ask_to_join: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    # noinspection PyDataclass
    mock_list_available_user_dicts.side_effect = [
        [],  # first call - no newbies
        [asdict(UserStateMachine(
            user_id='unavailable_user_id',
            state=UserState.DO_NOT_DISTURB,
            newbie=False,
        ))],  # second call - some veteran in not a valid state (dynamodb query malfunction?)
    ]

    _original_format_exception = traceback.format_exception

    def _wrap_format_exception(*args, **kwargs) -> List[Text]:
        _original_format_exception(*args, **kwargs)  # make sure parameters don't cause the original function to crash
        return ['stack', 'trace', 'goes', 'here']

    with patch('traceback.format_exception') as mock_traceback_format_exception:
        mock_traceback_format_exception.side_effect = _wrap_format_exception

        actual_events = await actions.ActionFindPartner().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'error'),
        SlotSet(
            'swiper_error',
            'InvalidSwiperStateError("randomly chosen partner \'unavailable_user_id\' '
            'is in a wrong state: \'do_not_disturb\'")',
        ),
        SlotSet('swiper_error_trace', 'stacktracegoeshere'),
        SlotSet('swiper_state', 'ok_to_chitchat'),
        SlotSet('partner_id', None),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_error',
        'template': 'utter_error',
        'text': None,
    }]

    mock_asyncio_sleep.assert_called_once_with(1.1)
    assert mock_list_available_user_dicts.mock_calls == [
        call(exclude_user_id='unit_test_user', newbie=True),
        call(exclude_user_id='unit_test_user', newbie=False),
    ]
    mock_rasa_callback_ask_to_join.assert_not_called()

    user_vault = UserVault()
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='ok_to_chitchat',
        partner_id=None,
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('time.time', Mock(return_value=1619945501))
async def test_action_ask_to_join(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    action = actions.ActionAskToJoin()
    assert action.name() == 'action_ask_to_join'

    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',  # receiver of the ask
        state='ok_to_chitchat',
        partner_id=None,
        newbie=True,
    ))

    tracker.add_slots([
        SlotSet('partner_id', 'an_asker'),
    ])

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'success'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'asked_to_join'),
        SlotSet('partner_id', 'an_asker'),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_someone_wants_to_chat',
        'template': 'utter_someone_wants_to_chat',
        'text': None,
    }]

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',  # receiver of the ask
        state='asked_to_join',
        partner_id='an_asker',
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('time.time', Mock(return_value=1619945501))
@patch('actions.daily_co.create_room', wraps=daily_co.create_room)
async def test_action_create_room(
        wrap_daily_co_create_room: AsyncMock,
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        daily_co_create_room_expected_call: Tuple[Text, call],
        new_room1: Dict[Text, Any],
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
        external_intent_response: Dict[Text, Any],
) -> None:
    mock_daily_co = AsyncMock(return_value=CallbackResult(payload=new_room1))
    mock_aioresponses.post(
        daily_co_create_room_expected_call[0],
        callback=mock_daily_co,
    )

    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'an_asker',
        'EXTERNAL_join_room',
        {
            'partner_id': 'unit_test_user',
            'room_url': 'https://swipy.daily.co/pytestroom',
        },
    )
    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=external_intent_response))
    mock_aioresponses.post(expected_rasa_url, callback=mock_rasa_callbacks)

    action = actions.ActionCreateRoom()
    assert action.name() == 'action_create_room'

    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='an_asker',
        state='waiting_partner_answer',
        partner_id='unit_test_user',
        newbie=True,
    ))
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',  # receiver of the ask
        state='asked_to_join',
        partner_id='an_asker',
        newbie=True,
    ))

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'room_url_ready'),
        SlotSet('room_url', 'https://swipy.daily.co/pytestroom'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),
        SlotSet('partner_id', None),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_room_url',
        'template': 'utter_room_url',
        'text': None,
        'room_url': 'https://swipy.daily.co/pytestroom',
    }]

    assert mock_daily_co.mock_calls == [daily_co_create_room_expected_call[1]]
    # make sure correct sender_id was passed (for logging purposes)
    wrap_daily_co_create_room.assert_called_once_with('unit_test_user')

    assert mock_rasa_callbacks.mock_calls == [expected_rasa_call]

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',  # receiver of the ask
        state='ok_to_chitchat',  # user joined the chat and ok_to_chitchat merely allows them to be invited again later
        partner_id=None,
        newbie=False,  # accepting the very first video chitchat graduates the user from newbie
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('partner', [
    UserStateMachine(
        user_id='an_asker',
        state='waiting_partner_answer',
        partner_id='a_completely_different_user',
        newbie=True,
    ),
    UserStateMachine(
        user_id='an_asker',
        state='ok_to_chitchat',
        partner_id='unit_test_user',
        newbie=True,
    ),
])
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('time.time', Mock(return_value=1619945501))
@patch('actions.rasa_callbacks.join_room')
@patch('actions.daily_co.create_room')
async def test_action_create_room_partner_not_waiting(
        mock_daily_co_create_room: AsyncMock,
        mock_rasa_callback_join_room: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        partner: UserStateMachine,
) -> None:
    user_vault = UserVault()
    user_vault.save(partner)
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',  # receiver of the ask
        state='asked_to_join',
        partner_id='an_asker',
        newbie=True,
    ))

    actual_events = await actions.ActionCreateRoom().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_not_waiting_anymore'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),
        SlotSet('partner_id', None),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_partner_already_gone',
        'template': 'utter_partner_already_gone',
        'text': None,
    }]

    mock_daily_co_create_room.assert_not_called()
    mock_rasa_callback_join_room.assert_not_called()

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',  # receiver of the ask
        state='ok_to_chitchat',
        partner_id=None,
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('current_user, expected_swiper_error', [
    (
            UserStateMachine(
                user_id='unit_test_user',
                state='asked_to_join',
                partner_id=None,
                newbie=True,
            ),
            'InvalidSwiperStateError("current user \'unit_test_user\' cannot join the room '
            'because current_user.partner_id is None")',
    ),
    (
            UserStateMachine(
                user_id='unit_test_user',
                state='ok_to_chitchat',
                partner_id='an_asker',
                newbie=True,
            ),
            'InvalidSwiperStateError("current user \'unit_test_user\' is not in state \'asked_to_join\', '
            'hence cannot join the room (actual state is \'ok_to_chitchat\')")',
    ),
])
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('actions.rasa_callbacks.join_room')
@patch('actions.daily_co.create_room')
async def test_action_create_room_invalid_state(
        mock_daily_co_create_room: AsyncMock,
        mock_rasa_callback_join_room: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        current_user: UserStateMachine,
        expected_swiper_error: Text,
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='an_asker',
        state='waiting_partner_answer',
        partner_id='unit_test_user',
        newbie=True,
    ))
    user_vault.save(current_user)

    actions.SEND_ERROR_STACK_TRACE_TO_SLOT = False

    actual_events = await actions.ActionCreateRoom().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'error'),
        SlotSet('swiper_error', expected_swiper_error),
        SlotSet('swiper_state', current_user.state),
        SlotSet('partner_id', current_user.partner_id),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_error',
        'template': 'utter_error',
        'text': None,
    }]

    mock_daily_co_create_room.assert_not_called()
    mock_rasa_callback_join_room.assert_not_called()

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == current_user  # current user should not be changed


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('time.time', Mock(return_value=1619945501))
async def test_action_join_room(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    action = actions.ActionJoinRoom()
    assert action.name() == 'action_join_room'

    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',  # the asker
        state='waiting_partner_answer',
        partner_id='partner_that_accepted',
        newbie=True,
    ))

    tracker.add_slots([
        SlotSet('partner_id', 'partner_that_accepted'),
    ])

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'success'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),
        SlotSet('partner_id', None),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_found_partner_room_url',
        'template': 'utter_found_partner_room_url',
        'text': None,
    }]

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',  # the asker
        state='ok_to_chitchat',  # user joined the chat and ok_to_chitchat merely allows them to be invited again later
        partner_id=None,
        newbie=False,  # accepting the very first video chitchat graduates the user from newbie
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('time.time', Mock(return_value=1619945501))
async def test_action_become_ok_to_chitchat(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    action = actions.ActionBecomeOkToChitchat()
    assert action.name() == 'action_become_ok_to_chitchat'

    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state='do_not_disturb',
        partner_id='the_asker',
        newbie=True,
    ))

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'success'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),
        SlotSet('partner_id', None),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_thanks_for_being_ok_to_chitchat',
        'template': 'utter_thanks_for_being_ok_to_chitchat',
        'text': None,
    }]

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='ok_to_chitchat',
        partner_id=None,
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('time.time', Mock(return_value=1619945501))
@pytest.mark.parametrize('current_user, asker, find_partner_call_expected', [
    (
            UserStateMachine(
                user_id='unit_test_user',
                state='asked_to_join',
                partner_id='the_asker',
                newbie=True,
            ),
            UserStateMachine(
                user_id='the_asker',
                state='ok_to_chitchat',  # the asker isn't waiting for the current user anymore
                partner_id=None,
                newbie=True,
            ),
            False,  # find_partner should not be called for "the asker"
    ),
    (
            UserStateMachine(
                user_id='unit_test_user',
                state='asked_to_join',
                partner_id='the_asker',
                newbie=True,
            ),
            UserStateMachine(
                user_id='the_asker',
                state='waiting_partner_answer',
                partner_id='someone_else',  # the asker is already waiting for someone else at this point
                newbie=True,
            ),
            False,  # find_partner should not be called for "the asker"
    ),
    (
            UserStateMachine(
                user_id='unit_test_user',
                state='waiting_partner_answer',  # current user is not even asked
                partner_id='the_asker',  # TODO oleksandr: this use case is weird - think it through and comment
                newbie=True,
            ),
            UserStateMachine(
                user_id='the_asker',
                state='waiting_partner_answer',
                partner_id='unit_test_user',
                newbie=True,
            ),
            False,  # find_partner should not be called for "the asker"
    ),
    (
            UserStateMachine(
                user_id='unit_test_user',
                state='asked_to_join',
                partner_id='the_asker',
                newbie=True,
            ),
            UserStateMachine(
                user_id='the_asker',
                state='waiting_partner_answer',
                partner_id='unit_test_user',
                newbie=True,
            ),
            True,  # the asker is actually waiting for the current user to answer - find_partner should be called
    ),
])
async def test_action_do_not_disturb(
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
        external_intent_response: Dict[Text, Any],
        current_user: UserStateMachine,
        asker: UserStateMachine,
        find_partner_call_expected: bool,
) -> None:
    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'the_asker',
        'EXTERNAL_find_partner',
        {},
    )
    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=external_intent_response))
    mock_aioresponses.post(expected_rasa_url, callback=mock_rasa_callbacks)

    action = actions.ActionDoNotDisturb()
    assert action.name() == 'action_do_not_disturb'

    user_vault = UserVault()
    user_vault.save(current_user)
    user_vault.save(asker)

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'success'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'do_not_disturb'),
        SlotSet('partner_id', None),
    ]
    assert dispatcher.messages == []

    if find_partner_call_expected:
        assert mock_rasa_callbacks.mock_calls == [expected_rasa_call]
    else:
        mock_rasa_callbacks.assert_not_called()

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='do_not_disturb',
        partner_id=None,
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
    )
    assert user_vault.get_user('the_asker') == asker  # ActionDoNotDisturb should not change the asker state directly
