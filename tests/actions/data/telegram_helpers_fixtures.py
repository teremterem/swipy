from typing import Dict, Text, Any

import pytest


@pytest.fixture
def blabla() -> Dict[Text, Any]:
    'getUserProfilePhotos'
    return {'limit': 1, 'user_id': '210723289'}


def telegram_user_profile_photo() -> Dict[Text, Any]:
    return {
        'ok': True,
        'result': {'photos': [[{
            'file_id': 'AgACAgIAAxkDAAIJDWC6QX0wTayXFTpGk5B6DfTNXZZLAAIhqDEb2WGPDERGNBe_IjKwp_XVli4AAwEAAwIAA2EAA6z9BQABHwQ',
            'file_size': 10450,
            'file_unique_id': 'AQADp_XVli4AA6z9BQAB',
            'height': 160,
            'width': 160},
            {
                'file_id': 'AgACAgIAAxkDAAIJDWC6QX0wTayXFTpGk5B6DfTNXZZLAAIhqDEb2WGPDERGNBe_IjKwp_XVli4AAwEAAwIAA2IAA639BQABHwQ',
                'file_size': 33842,
                'file_unique_id': 'AQADp_XVli4AA639BQAB',
                'height': 320,
                'width': 320},
            {
                'file_id': 'AgACAgIAAxkDAAIJDWC6QX0wTayXFTpGk5B6DfTNXZZLAAIhqDEb2WGPDERGNBe_IjKwp_XVli4AAwEAAwIAA2MAA679BQABHwQ',
                'file_size': 102191,
                'file_unique_id': 'AQADp_XVli4AA679BQAB',
                'height': 640,
                'width': 640}]],
            'total_count': 4}}


def no_telegram_user_profile_photo() -> Dict[Text, Any]:
    return {'ok': True, 'result': {'photos': [], 'total_count': 0}}


def telegram_user_profile_photo_no_files() -> Dict[Text, Any]:
    return {'ok': True, 'result': {'photos': [[]]}}
