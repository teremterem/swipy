from dataclasses import asdict
from typing import Dict, Text, Any, List
from unittest.mock import patch, AsyncMock, MagicMock, call, Mock

import pytest
from rasa_sdk import Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType
from rasa_sdk.executor import CollectingDispatcher

from actions import actions
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
    mock_ddb_get_user.assert_called_once_with('unit_test_user')

    await action.run(dispatcher, tracker, domain)
    assert mock_ddb_get_user.call_count == 2  # new run should use new cache
    mock_ddb_get_user.assert_called_with('unit_test_user')


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
async def test_swiper_state_slot_is_set_after_action_run(
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

            _user_vault.save(UserStateMachine(
                user_id=_current_user.user_id,
                state=UserState.OK_TO_CHITCHAT,
            ))  # save a completely different instance of the current user
            return []

    action = SomeSwiperAction()

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),  # the action is expected to use the most recent value of state
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
        SlotSet('another-slot', 'value2'),
    ])

    domain['session_config']['carry_over_slots_to_new_session'] = carry_over_slots_to_new_session
    expected_events = expected_events + [
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),  # state taken from UserVault rather than carried over
        ActionExecuted(action_name='action_listen'),
    ]

    assert await actions.ActionSessionStart().run(dispatcher, tracker, domain) == expected_events
    assert dispatcher.messages == []


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('actions.rasa_callbacks.ask_to_join')
@patch.object(UserVault, 'get_random_available_user')
async def test_action_find_partner_newbie(
        mock_get_random_available_user: MagicMock,
        mock_rasa_callback_ask_to_join: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        user_vault: UserVault,
        available_newbie1: UserStateMachine,
) -> None:
    mock_get_random_available_user.return_value = available_newbie1

    action = actions.ActionFindPartner()
    assert action.name() == 'action_find_partner'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_has_been_asked'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'waiting_partner_answer'),
    ]
    assert dispatcher.messages == []

    mock_get_random_available_user.assert_called_once_with(exclude_user_id='unit_test_user', newbie=True)
    mock_rasa_callback_ask_to_join.assert_called_once_with('available_newbie_id1', 'unit_test_user')

    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='waiting_partner_answer',
        partner_id='available_newbie_id1',
        newbie=True,
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('actions.rasa_callbacks.ask_to_join')
@patch.object(UserVault, 'get_random_available_user')
async def test_action_find_partner_veteran(
        mock_get_random_available_user: MagicMock,
        mock_rasa_callback_ask_to_join: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        user_vault: UserVault,
        available_veteran1: UserStateMachine,
) -> None:
    mock_get_random_available_user.side_effect = [None, available_veteran1]

    actual_events = await actions.ActionFindPartner().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_has_been_asked'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'waiting_partner_answer'),
    ]
    assert dispatcher.messages == []

    assert mock_get_random_available_user.mock_calls == [
        call(exclude_user_id='unit_test_user', newbie=True),
        call(exclude_user_id='unit_test_user', newbie=False),
    ]
    mock_rasa_callback_ask_to_join.assert_called_once_with('available_veteran_id1', 'unit_test_user')

    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='waiting_partner_answer',
        partner_id='available_veteran_id1',
        newbie=True,
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('actions.rasa_callbacks.ask_to_join')
@patch.object(UserVault, 'get_random_available_user')
async def test_action_find_partner_no_one(
        mock_get_random_available_user: MagicMock,
        mock_rasa_callback_ask_to_join: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        user_vault: UserVault,
) -> None:
    mock_get_random_available_user.side_effect = [None, None]

    actual_events = await actions.ActionFindPartner().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_was_not_found'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'ok_to_chitchat'),
    ]
    assert dispatcher.messages == []

    assert mock_get_random_available_user.mock_calls == [
        call(exclude_user_id='unit_test_user', newbie=True),
        call(exclude_user_id='unit_test_user', newbie=False),
    ]
    mock_rasa_callback_ask_to_join.assert_not_called()

    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='ok_to_chitchat',
        partner_id=None,
        newbie=True,
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('actions.actions.stack_trace_to_str', Mock(return_value='stack trace goes here'))
@patch('actions.rasa_callbacks.ask_to_join')
@patch.object(UserVault, 'get_random_available_user')
async def test_action_find_partner_invalid_state(
        mock_get_random_available_user: MagicMock,
        mock_rasa_callback_ask_to_join: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        user_vault: UserVault,
) -> None:
    mock_get_random_available_user.side_effect = [None, UserStateMachine(
        user_id='unavailable_user_id',
        state=UserState.DO_NOT_DISTURB,
    )]

    actual_events = await actions.ActionFindPartner().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'error'),
        SlotSet(
            'swiper_error',
            'InvalidSwiperStateError("randomly chosen partner \'unavailable_user_id\' '
            'is in a wrong state: \'do_not_disturb\'")',
        ),
        SlotSet('swiper_error_trace', 'stack trace goes here'),
        SlotSet('swiper_state', 'ok_to_chitchat'),
    ]
    assert dispatcher.messages == []

    assert mock_get_random_available_user.mock_calls == [
        call(exclude_user_id='unit_test_user', newbie=True),
        call(exclude_user_id='unit_test_user', newbie=False),
    ]
    mock_rasa_callback_ask_to_join.assert_not_called()

    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='ok_to_chitchat',
        partner_id=None,
        newbie=True,
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table')
async def test_action_ask_to_join(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    action = actions.ActionAskToJoin()
    assert action.name() == 'action_ask_to_join'

    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='an_asker',
        state='waiting_partner_answer',
        partner_id='unit_test_user',
        newbie=True,
    ))
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
    assert user_vault.get_user('an_asker') == UserStateMachine(  # no changes expected
        user_id='an_asker',
        state='waiting_partner_answer',
        partner_id='unit_test_user',
        newbie=True,
    )
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',  # receiver of the ask
        state='asked_to_join',
        partner_id='an_asker',
        newbie=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('asker, receiver, error_log_params', [
    (
            UserStateMachine(
                user_id='an_asker',
                state='waiting_partner_answer',
                partner_id='unit_test_user',
                newbie=True,
            ),
            UserStateMachine(
                user_id='unit_test_user',
                state='do_not_disturb',
                partner_id=None,
                newbie=True,
            ),
            [
                'current user %r is not in state %r, hence cannot be asked (actual state is %r)',
                'unit_test_user',
                'ok_to_chitchat',
                'do_not_disturb',
            ],
    ),
])
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch.object(actions.logger, 'error')
async def test_action_ask_to_join_invalid(
        logger_error_mock: MagicMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        asker: UserStateMachine,
        receiver: UserStateMachine,
        error_log_params: List[Text],
) -> None:
    user_vault = UserVault()
    user_vault.save(asker)
    user_vault.save(receiver)

    tracker.add_slots([
        SlotSet('partner_id', 'an_asker'),
    ])

    actual_events = await actions.ActionAskToJoin().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', receiver.state),
    ]
    assert dispatcher.messages == []  # receiver should not be notified about these failures

    logger_error_mock.assert_called_once_with(*error_log_params)

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('an_asker') == asker  # no changes expected
    assert user_vault.get_user('unit_test_user') == receiver  # no changes expected


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('actions.rasa_callbacks.invite_chitchat_partner')
@patch('actions.daily_co.create_room')
@patch.object(UserVault, 'get_random_available_user')
async def test_action_create_room_experimental(
        mock_get_random_available_user: MagicMock,
        mock_daily_co_create_room: AsyncMock,
        mock_rasa_callback_invite_chitchat_partner: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        user3: UserStateMachine,
        new_room1: Dict[Text, Any],
) -> None:
    mock_get_random_available_user.return_value = user3
    mock_daily_co_create_room.return_value = new_room1

    action = actions.ActionCreateRoomExperimental()
    assert action.name() == 'action_create_room_experimental'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('room_url', 'https://swipy.daily.co/pytestroom'),
        SlotSet('swiper_error', None),
        SlotSet('swiper_error_trace', None),
        SlotSet('swiper_state', 'new'),
    ]

    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_video_link',
        'room_url': 'https://swipy.daily.co/pytestroom',
        'template': 'utter_video_link',
        'text': None,
    }]
    mock_get_random_available_user.assert_called_once_with('unit_test_user')
    mock_rasa_callback_invite_chitchat_partner.assert_called_once_with(
        'existing_user_id3',
        'https://swipy.daily.co/pytestroom',
    )
