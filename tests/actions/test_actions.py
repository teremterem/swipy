from typing import Dict, Text, Any
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions import actions
from actions.user_state_machine import user_vault, UserStateMachine


@pytest.mark.asyncio
@patch('actions.actions.create_room')
@patch.object(user_vault, 'get_random_available_user')
async def test_action_create_room(
        mock_get_random_available_user: MagicMock,
        mock_create_room: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict,
        user3: UserStateMachine,
        new_room1: Dict[Text, Any],
) -> None:
    mock_get_random_available_user.return_value = user3
    mock_create_room.return_value = new_room1

    action = actions.ActionCreateRoom()
    assert action.name() == 'action_create_room'

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
