from typing import Dict, Text, Any

import pytest


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
