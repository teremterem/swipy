from typing import Dict, Text, Any
from unittest.mock import patch, MagicMock, call

import pytest

from actions import telegram_helpers


@patch('telebot.apihelper._make_request')
def test_get_user_profile_photo_file_id(
        mock_make_request: MagicMock,
        telegram_user_profile_photo: Dict[Text, Any],
        telegram_user_profile_photo_make_request_call: call,
) -> None:
    mock_make_request.return_value = telegram_user_profile_photo

    file_id = telegram_helpers.get_user_profile_photo_file_id('unit_test_user')
    assert file_id == 'biggest_file_id'

    assert mock_make_request.mock_calls == [
        telegram_user_profile_photo_make_request_call,
    ]


@pytest.mark.parametrize('make_request_return_value', [
    {'photos': [], 'total_count': 0},
    {'photos': [], 'total_count': 3},
    {'photos': [[]], 'total_count': 4},
])
@patch('telebot.apihelper._make_request')
def test_get_user_profile_photo_file_id_none(
        mock_make_request: MagicMock,
        make_request_return_value: Dict[Text, Any],
        telegram_user_profile_photo_make_request_call: call,
) -> None:
    mock_make_request.return_value = make_request_return_value

    file_id = telegram_helpers.get_user_profile_photo_file_id('unit_test_user')
    assert file_id is None

    assert mock_make_request.mock_calls == [
        telegram_user_profile_photo_make_request_call,
    ]
