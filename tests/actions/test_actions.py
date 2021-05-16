from typing import Dict, Text, Any
from unittest.mock import patch, AsyncMock

import pytest
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions import actions


@pytest.mark.asyncio
@patch('actions.actions.create_room')
async def test_action_create_room(
        mock_create_room: AsyncMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict,
        new_room1: Dict[Text, Any],
) -> None:
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
