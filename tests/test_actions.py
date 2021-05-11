import pytest
from aioresponses import CallbackResult, aioresponses
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions import actions


@pytest.mark.asyncio
async def test_action_create_room(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict,
        mock_aioresponse: aioresponses,
):
    def daily_co_callback_mock(url, headers=None, json=None, **kwargs):
        assert headers == {
            'Authorization': 'Bearer test-daily-co-api-token',
        }
        assert json == {
            'privacy': 'public',
            'properties': {
                'enable_network_ui': False,
                'enable_prejoin_ui': True,
                'enable_new_call_ui': True,
                'enable_screenshare': True,
                'enable_chat': True,
                'start_video_off': False,
                'start_audio_off': False,
                'owner_only_broadcast': False,
                'lang': 'en',
            },
        }
        return CallbackResult(
            payload={
                'api_created': True,
                'config': {
                    'enable_chat': True,
                    'enable_network_ui': False,
                    'enable_new_call_ui': True,
                    'enable_prejoin_ui': True,
                    'lang': 'en',
                },
                'created_at': '2021-05-09T16:41:17.424Z',
                'id': 'eeeeeeee-1111-2222-3333-ffffffffffff',
                'name': 'pytestroom',
                'privacy': 'public',
                'url': 'https://swipy.daily.co/pytestroom',
            },
        )

    mock_aioresponse.post(
        'https://api.daily.co/v1/rooms',
        callback=daily_co_callback_mock,
    )

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
