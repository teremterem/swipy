from typing import Dict, Text, Any
from unittest.mock import call

import pytest


@pytest.fixture
def telegram_user_profile_photo_make_request_call() -> call:
    return call(
        'unittest:telegramtoken',
        'getUserProfilePhotos',
        params={
            'limit': 1,
            'user_id': 'unit_test_user',
        },
    )


@pytest.fixture
def telegram_user_profile_photo() -> Dict[Text, Any]:
    return {
        'photos': [
            [
                {
                    'file_id': 'smallest_file_id',
                    'file_size': 10450,
                    'file_unique_id': 'smallest_file_unique_id',
                    'height': 160,
                    'width': 160,
                },
                {
                    'file_id': 'biggest_file_id',
                    'file_size': 102191,
                    'file_unique_id': 'biggest_file_unique_id',
                    'height': 640,
                    'width': 640,
                },
                {
                    'file_id': 'medium_file_id',
                    'file_size': 33842,
                    'file_unique_id': 'medium_file_unique_id',
                    'height': 320,
                    'width': 320,
                },
            ],
        ],
        'total_count': 4,
    }
