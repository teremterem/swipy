from typing import Dict, Text, Any
from unittest.mock import patch, MagicMock

from actions import telegram_helpers


@patch('telebot.apihelper._make_request')
def test_get_user_profile_photo_file_id(
        mock_make_request: MagicMock,
        telegram_user_profile_photo: Dict[Text, Any],
) -> None:
    mock_make_request.return_value = telegram_user_profile_photo

    file_id = telegram_helpers.get_user_profile_photo_file_id('some_user_id')
    assert file_id == 'biggest_file_id'

    mock_make_request.assert_called_once_with(
        'unittest:telegramtoken',
        'getUserProfilePhotos',
        params={
            'limit': 1,
            'user_id': 'some_user_id',
        },
    )
