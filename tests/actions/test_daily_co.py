from typing import Dict, Text, Any, Tuple, Optional
from unittest.mock import AsyncMock, call

import pytest
from aioresponses import aioresponses, CallbackResult

from actions import daily_co
from actions.utils import SwiperDailyCoError


@pytest.mark.asyncio
async def test_create_room(
        mock_aioresponses: aioresponses,
        daily_co_create_room_expected_call: Tuple[Text, call],
        new_room1: Dict[Text, Any],
) -> None:
    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=new_room1))
    mock_aioresponses.post(
        daily_co_create_room_expected_call[0],
        callback=mock_rasa_callbacks,
    )

    assert await daily_co.create_room('some_sender_id') == new_room1
    assert mock_rasa_callbacks.mock_calls == [daily_co_create_room_expected_call[1]]


@pytest.mark.asyncio
@pytest.mark.parametrize('url_missing', ['', None, 'del', 'faiiiil'])
async def test_create_room_url_not_returned(
        mock_aioresponses: aioresponses,
        url_missing: Optional[Text],
        daily_co_create_room_expected_call: Tuple[Text, call],
        new_room1: Dict[Text, Any],
) -> None:
    if url_missing == 'del':
        del new_room1['url']
    else:
        new_room1['url'] = url_missing

    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=new_room1))
    mock_aioresponses.post(
        daily_co_create_room_expected_call[0],
        callback=mock_rasa_callbacks,
    )

    with pytest.raises(SwiperDailyCoError):
        await daily_co.create_room('some_sender_id')
    assert mock_rasa_callbacks.mock_calls == [daily_co_create_room_expected_call[1]]
