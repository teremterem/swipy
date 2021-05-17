from typing import Dict, Text, Any
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions.actions import ActionFindSomeone, ActionMakeUserAvailable
from actions.user_vault import user_vault, UserStateMachine


@pytest.mark.asyncio
@patch.object(user_vault, 'get_user')
async def test_action_make_user_available(
        mock_get_user: MagicMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict,
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
        domain: DomainDict,
        user3: UserStateMachine,
        new_room1: Dict[Text, Any],
) -> None:
    mock_get_random_available_user.return_value = user3
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
