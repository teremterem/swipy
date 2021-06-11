from typing import Callable, Text, Dict, Any, Tuple
from unittest.mock import call

import pytest
from aioresponses.core import RequestCall
from yarl import URL


@pytest.fixture
def rasa_callbacks_join_room_expected_req(rasa_callbacks_expected_req_builder: Callable[
    [Text, Text, Dict[Text, Any]], Tuple[Tuple[Text, URL], RequestCall]
]) -> Tuple[Tuple[Text, URL], RequestCall]:
    expected_req_key, expected_req_call = rasa_callbacks_expected_req_builder(
        'an_asker',
        'EXTERNAL_join_room',
        {
            'partner_id': 'unit_test_user',
            'room_url': 'https://swipy.daily.co/pytestroom',
        },
    )
    return expected_req_key, expected_req_call


@pytest.fixture
def rasa_callbacks_ask_if_ready_expected_req(rasa_callbacks_expected_req_builder: Callable[
    [Text, Text, Dict[Text, Any]], Tuple[Tuple[Text, URL], RequestCall]
]) -> Tuple[Tuple[Text, URL], RequestCall]:
    expected_req_key, expected_req_call = rasa_callbacks_expected_req_builder(
        'an_asker',
        'EXTERNAL_ask_if_ready',
        {
            'partner_id': 'unit_test_user',
            'partner_photo_file_id': 'biggest_profile_pic_file_id',
        },
    )
    return expected_req_key, expected_req_call
