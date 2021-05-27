from typing import Dict, Text, Any, Tuple
from unittest.mock import AsyncMock, call

import pytest
from aioresponses import aioresponses, CallbackResult

from actions import daily_co


@pytest.mark.asyncio
async def test_create_room(
        daily_co_create_room_expected_call: Tuple[Text, call],
        mock_aioresponses: aioresponses,
        new_room1: Dict[Text, Any],
) -> None:
    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=new_room1))
    mock_aioresponses.post(
        daily_co_create_room_expected_call[0],
        callback=mock_rasa_callbacks,
    )

    assert await daily_co.create_room('some_sender_id') == new_room1
    assert mock_rasa_callbacks.mock_calls == [daily_co_create_room_expected_call[1]]
