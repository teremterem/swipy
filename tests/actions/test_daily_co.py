import re
from typing import Dict, Text, Any, Tuple, Optional, Callable
from unittest.mock import patch, Mock

import pytest
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from yarl import URL

from actions import daily_co
from actions.utils import SwiperDailyCoError


@pytest.mark.asyncio
@patch('time.time', Mock(return_value=1619945501))  # "now"
async def test_create_room(
        mock_aioresponses: aioresponses,
        daily_co_create_room_expected_req: Tuple[Text, RequestCall],
        new_room1: Dict[Text, Any],
) -> None:
    mock_aioresponses.post(re.compile(r'.*'), payload=new_room1)

    assert await daily_co.create_room('some_sender_id') == new_room1
    assert mock_aioresponses.requests == {daily_co_create_room_expected_req[0]: [daily_co_create_room_expected_req[1]]}


@pytest.mark.asyncio
@pytest.mark.parametrize('url_missing', ['', None, 'del'])
@patch('time.time', Mock(return_value=1619945501))  # "now"
async def test_create_room_url_not_returned(
        mock_aioresponses: aioresponses,
        url_missing: Optional[Text],
        daily_co_create_room_expected_req: Tuple[Text, RequestCall],
        new_room1: Dict[Text, Any],
) -> None:
    if url_missing == 'del':
        del new_room1['url']
    else:
        new_room1['url'] = url_missing

    mock_aioresponses.post(re.compile(r'.*'), payload=new_room1)

    with pytest.raises(SwiperDailyCoError):
        await daily_co.create_room('some_sender_id')
    assert mock_aioresponses.requests == {daily_co_create_room_expected_req[0]: [daily_co_create_room_expected_req[1]]}


@pytest.mark.asyncio
@pytest.mark.parametrize('response_payload, emulate_status, expected_result', [
    ({'deleted': True}, 200, True),
    ({'deleted': True, 'room_name': 'wrong_room_name'}, 200, True),  # we don't bother verifying the room name
    ({'deleted': True, 'room_name': 'correct_room_name'}, 200, True),  # we don't bother verifying the room name
    ({}, 200, False),
    ({'deleted': False}, 200, False),
    ({'deleted': False, 'room_name': 'correct_room_name'}, 200, False),
    ({'deleted': True}, 404, False),  # attempt to delete expired room
    ({'deleted': True, 'room_name': 'correct_room_name'}, 404, False),  # attempt to delete expired room
    (None, 500, False),  # emulate non-json payload
])
@patch('time.time', Mock(return_value=1619945501))  # "now"
async def test_delete_room(
        mock_aioresponses: aioresponses,
        daily_co_delete_room_expected_req_builder: Callable[[Text], Tuple[Tuple[Text, URL], RequestCall]],
        response_payload: Optional[Dict[Text, Any]],
        emulate_status: int,
        expected_result: bool,
) -> None:
    expected_req_key, expected_req_call = daily_co_delete_room_expected_req_builder('correct_room_name')

    if response_payload is None:
        # emulate HTTP 500
        mock_aioresponses.delete(re.compile(r'.*'), status=500, body='<html></html>')
    else:
        mock_aioresponses.delete(re.compile(r'.*'), payload=response_payload)

    actual_result = await daily_co.delete_room('correct_room_name')
    assert actual_result == expected_result

    assert mock_aioresponses.requests == {expected_req_key: [expected_req_call]}
