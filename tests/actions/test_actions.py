from typing import Dict, Text, Any, List
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from rasa_sdk import Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType
from rasa_sdk.executor import CollectingDispatcher

from actions.actions import ActionSessionStart, ActionMakeUserAvailable, ActionFindSomeone
from actions.user_state_machine import UserStateMachine
from actions.user_vault import user_vault


@pytest.mark.asyncio
async def test_action_session_start_without_slots(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    action = ActionSessionStart()
    assert action.name() == 'action_session_start'

    tracker.slots.clear()
    events = await action.run(dispatcher, tracker, domain)
    assert events == [SessionStarted(), ActionExecuted('action_listen')]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "carry_over_slots_to_new_session, expected_events",
    [
        (
                True,
                [
                    SessionStarted(),
                    SlotSet("session_started_metadata", None),  # comes from tests/actions/data/initial_tracker.json
                    SlotSet("room_link", None),  # comes from tests/actions/data/initial_tracker.json
                    SlotSet("my_slot", "value"),
                    SlotSet("another-slot", "value2"),
                    ActionExecuted(action_name='action_listen'),
                ],
        ),
        (
                False,
                [SessionStarted(), ActionExecuted(action_name='action_listen')],
        ),
    ],
)
async def test_action_session_start_with_slots(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        carry_over_slots_to_new_session: bool,
        expected_events: List[EventType],
):
    # set a few slots on tracker
    tracker.add_slots([
        SlotSet("my_slot", "value"),
        SlotSet("another-slot", "value2"),
    ])

    domain['session_config']['carry_over_slots_to_new_session'] = carry_over_slots_to_new_session

    events = await ActionSessionStart().run(dispatcher, tracker, domain)
    assert events == expected_events


@pytest.mark.asyncio
@patch.object(user_vault, 'get_user')
async def test_action_make_user_available(
        mock_get_user: MagicMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        unit_test_user: UserStateMachine,
) -> None:
    mock_get_user.return_value = unit_test_user

    action = ActionMakeUserAvailable()
    assert action.name() == 'action_make_user_available'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == []

    mock_get_user.assert_called_once_with('unit_test_user')


@pytest.mark.asyncio
@patch('actions.actions.invite_chitchat_partner')
@patch('actions.actions.create_room')
@patch.object(user_vault, 'get_random_available_user')
async def test_action_find_someone(
        mock_get_random_available_user: MagicMock,
        mock_create_room: AsyncMock,
        mock_invite_chitchat_partner: MagicMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        ddb_user3: UserStateMachine,
        new_room1: Dict[Text, Any],
) -> None:
    mock_get_random_available_user.return_value = ddb_user3
    mock_create_room.return_value = new_room1

    action = ActionFindSomeone()
    assert action.name() == 'action_find_someone'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == []

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
    mock_invite_chitchat_partner.assert_called_once_with('existing_user_id3', 'https://swipy.daily.co/pytestroom')
