from typing import Dict, Text, Any, Tuple, Callable
from urllib.parse import quote as urlencode

import pytest
from aioresponses.core import RequestCall
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
def daily_co_create_room_expected_req() -> Tuple[Tuple[Text, URL], RequestCall]:
    expected_req_key = ('POST', URL('https://api.daily-unittest.co/v1/rooms'))
    expected_req_call = RequestCall(
        args=(),
        kwargs={
            'data': None,
            'headers': {
                'Authorization': 'Bearer test-daily-co-api-token',
            },
            'json': {
                'privacy': 'public',
                'properties': {
                    'eject_at_room_exp': True,
                    'exp': 1619945501 + (30 * 60),
                    'max_participants': 3,
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
        },
    )
    return expected_req_key, expected_req_call


@pytest.fixture
def daily_co_delete_room_expected_req_builder() -> Callable[[Text], Tuple[Tuple[Text, URL], RequestCall]]:
    def _expected_request_builder(expected_room_name: Text):
        expected_req_key = ('DELETE', URL(f"https://api.daily-unittest.co/v1/rooms/{urlencode(expected_room_name)}"))
        expected_req_call = RequestCall(
            args=(),
            kwargs={
                'data': None,
                'headers': {
                    'Authorization': 'Bearer test-daily-co-api-token',
                },
            },
        )
        return expected_req_key, expected_req_call

    return _expected_request_builder
