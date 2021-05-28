from typing import Dict, Text, Any, Tuple
from unittest.mock import call

import pytest
from yarl import URL


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
def daily_co_create_room_expected_call() -> Tuple[Text, call]:
    expected_url = 'https://api.daily.co/v1/rooms'
    expected_call = call(
        URL(expected_url),
        allow_redirects=True,
        data=None,
        headers={
            'Authorization': 'Bearer test-daily-co-api-token',
        },
        json={
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
        },
    )

    return expected_url, expected_call
