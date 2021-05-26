from typing import Dict, Text, Any
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses, CallbackResult


@pytest.fixture
def new_room1() -> Dict[Text, Any]:
    return {
        'api_created': True,
        'config': {
            'enable_chat': True,
            'enable_network_ui': False,
            'enable_new_call_ui': True,
            'enable_prejoin_ui': False,
            'lang': 'en',
        },
        'created_at': '2021-05-09T16:41:17.424Z',
        'id': 'eeeeeeee-1111-2222-3333-ffffffffffff',
        'name': 'pytestroom',
        'privacy': 'public',
        'url': 'https://swipy.daily.co/pytestroom',
    }


@pytest.fixture
def mock_daily_co_create_room_aioresponses(
        mock_aioresponses: aioresponses,
        new_room1: Dict[Text, Any],
) -> AsyncMock:
    async def _daily_co_callback(url, headers=None, json=None, **kwargs):
        assert headers == {
            'Authorization': 'Bearer test-daily-co-api-token',
        }
        assert json == {
            'privacy': 'public',
            'properties': {
                'enable_network_ui': False,
                'enable_prejoin_ui': False,
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

    _mock_daily_co_create_room_aioresponses = AsyncMock(side_effect=_daily_co_callback)
    mock_aioresponses.post(
        'https://api.daily.co/v1/rooms',
        callback=_mock_daily_co_create_room_aioresponses,
    )

    return _mock_daily_co_create_room_aioresponses
