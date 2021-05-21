from dataclasses import asdict
from typing import Dict, Text, Any, List
from unittest.mock import patch, AsyncMock, MagicMock

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

            _user_vault.save_user(UserStateMachine(
                user_id=_current_user.user_id,
                state=UserState.OK_FOR_CHITCHAT,
            ))  # save a completely different instance of the current user
            return []

    action = SomeSwiperAction()

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_state', 'ok_for_chitchat'),  # the action is expected to use the most recent value of state
    ]


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
        SlotSet('swiper_state', 'new'),  # state taken from UserVault
        ActionExecuted('action_listen'),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize('carry_over_slots_to_new_session, expected_events', [
    (
            True,
            [
                SessionStarted(),
                SlotSet('session_started_metadata', None),  # comes from tests/actions/data/initial_tracker.json
                SlotSet('room_link', None),  # comes from tests/actions/data/initial_tracker.json
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
        state=UserState.OK_FOR_CHITCHAT,
    )))

    # set a few slots on tracker
    tracker.add_slots([
        SlotSet('my_slot', 'value'),
        SlotSet('swiper_state', 'do_not_disturb'),  # expected to be replaced rather than carried over
        SlotSet('another-slot', 'value2'),
    ])

    domain['session_config']['carry_over_slots_to_new_session'] = carry_over_slots_to_new_session
    expected_events = expected_events + [
        SlotSet('swiper_state', 'ok_for_chitchat'),  # state taken from UserVault rather than carried over
        ActionExecuted(action_name='action_listen'),
    ]

    assert await actions.ActionSessionStart().run(dispatcher, tracker, domain) == expected_events


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
@patch('actions.rasa_callbacks.ask_partner')
@patch.object(UserVault, 'get_random_available_user')
async def test_action_find_newbie_partner(
        mock_get_random_available_user: MagicMock,
        mock_rasa_callback_ask_partner: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        available_newbie1: UserStateMachine,
) -> None:
    mock_get_random_available_user.return_value = available_newbie1

    action = actions.ActionFindPartner()
    assert action.name() == 'action_find_partner'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_has_been_asked'),
        SlotSet('swiper_state', 'waiting_partner_answer'),  # state taken from UserVault
    ]

    assert dispatcher.messages == []
    mock_get_random_available_user.assert_called_once_with(exclude_user_id='unit_test_user', newbie=True)
    mock_rasa_callback_ask_partner.assert_called_once_with('available_newbie_id1')


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
        SlotSet('room_link', 'https://swipy.daily.co/pytestroom'),
        SlotSet('swiper_state', 'new'),  # state taken from UserVault (all "swiper" actions must do this)
    ]

    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_video_link',
        'room_link': 'https://swipy.daily.co/pytestroom',
        'template': 'utter_video_link',
        'text': None,
    }]
    mock_get_random_available_user.assert_called_once_with('unit_test_user')
    mock_rasa_callback_invite_chitchat_partner.assert_called_once_with(
        'existing_user_id3',
        'https://swipy.daily.co/pytestroom',
    )
