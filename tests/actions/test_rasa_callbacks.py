from typing import Dict, Text, Any, Callable
from unittest.mock import AsyncMock

import pytest

from actions import rasa_callbacks


@pytest.mark.asyncio
async def test_ask_to_join(
        patch_rasa_callbacks: Callable[[Text, Text, Dict[Text, Any]], AsyncMock],
        external_intent_response: Dict[Text, Any],
) -> None:
    mock_rasa_callbacks = patch_rasa_callbacks(
        'partner_id_to_ask',
        'EXTERNAL_ask_to_join',
        {
            'partner_id': 'id_of_asker',
        },
    )

    assert await rasa_callbacks.ask_to_join('id_of_asker', 'partner_id_to_ask') == external_intent_response
    mock_rasa_callbacks.assert_called_once()  # more detailed assertions are done by the fixture


@pytest.mark.asyncio
async def test_join_room(
        patch_rasa_callbacks: Callable[[Text, Text, Dict[Text, Any]], AsyncMock],
        external_intent_response: Dict[Text, Any],
) -> None:
    mock_rasa_callbacks = patch_rasa_callbacks(
        'a_receiving_user',
        'EXTERNAL_join_room',
        {
            'partner_id': 'a_sending_user',
            'room_url': 'https://room-unittest/url',
        },
    )

    assert await rasa_callbacks.join_room(
        'a_sending_user',
        'a_receiving_user',
        'https://room-unittest/url',
    ) == external_intent_response
    mock_rasa_callbacks.assert_called_once()  # more detailed assertions are done by the fixture


@pytest.mark.asyncio
async def test_find_partner(
        patch_rasa_callbacks: Callable[[Text, Text, Dict[Text, Any]], AsyncMock],
        external_intent_response: Dict[Text, Any],
) -> None:
    mock_rasa_callbacks = patch_rasa_callbacks(
        'a_receiving_user',
        'EXTERNAL_find_partner',
        {},
    )

    assert await rasa_callbacks.find_partner('some_sender_id', 'a_receiving_user') == external_intent_response
    mock_rasa_callbacks.assert_called_once()  # more detailed assertions are done by the fixture
