import pytest
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions import actions


@pytest.mark.asyncio
async def test_action_create_room(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict,
):
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
        'room_link': 'https://roomlink',
        'template': 'utter_video_link',
        'text': None,
    }]
