from typing import Dict, Text, Any
from unittest.mock import AsyncMock

import pytest

from actions.daily_co import create_room


@pytest.mark.asyncio
async def test_create_room(
        mock_daily_co_create_room_aioresponses: AsyncMock,
        new_room1: Dict[Text, Any],
) -> None:
    assert await create_room('some_sender_id') == new_room1
    mock_daily_co_create_room_aioresponses.assert_called_once()
