import re
from typing import Dict, Text, Any, Tuple, Optional
from unittest.mock import patch, Mock

import pytest
from aioresponses import aioresponses
from aioresponses.core import RequestCall

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
