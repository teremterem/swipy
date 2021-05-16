from typing import Dict, Text, Any

import pytest
from aioresponses import CallbackResult, aioresponses

from actions.daily_co import create_room


@pytest.mark.asyncio
async def test_create_room(
        mock_aioresponses: aioresponses,
        new_room1: Dict[Text, Any],
) -> None:
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
        return CallbackResult(payload=new_room1)

    mock_aioresponses.post(
        'https://api.daily.co/v1/rooms',
        callback=daily_co_callback_mock,
    )

    assert await create_room() == new_room1
