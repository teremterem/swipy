from typing import Callable, Text, Dict, Any, Tuple
from unittest.mock import call

import pytest


@pytest.fixture
def rasa_callbacks_join_room_expected_call(
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
) -> Tuple[Text, call]:
    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'an_asker',
        'EXTERNAL_join_room',
        {
            'partner_id': 'unit_test_user',
            'room_url': 'https://swipy.daily.co/pytestroom',
        },
    )
    return expected_rasa_url, expected_rasa_call


@pytest.fixture
def rasa_callbacks_join_room_ready_expected_call(
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
) -> Tuple[Text, call]:
    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'an_asker',
        'EXTERNAL_join_room_ready',
        {
            'partner_id': 'unit_test_user',
            'room_url': 'https://swipy.daily.co/pytestroom',
        },
    )
    return expected_rasa_url, expected_rasa_call


@pytest.fixture
def rasa_callbacks_ask_if_ready_expected_call(
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
) -> Tuple[Text, call]:
    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'an_asker',
        'EXTERNAL_ask_if_ready',
        {
            'partner_id': 'unit_test_user',
        },
    )
    return expected_rasa_url, expected_rasa_call
