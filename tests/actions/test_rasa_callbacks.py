from typing import Dict, Text, Any, Callable, Tuple
from unittest.mock import AsyncMock, call

import pytest
from aioresponses import CallbackResult, aioresponses

from actions import rasa_callbacks


@pytest.mark.asyncio
async def test_ask_to_join(
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> None:
    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'partner_id_to_ask',
        'EXTERNAL_ask_to_join',
        {
            'partner_id': 'id_of_asker',
        },
    )
    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=external_intent_response))
    mock_aioresponses.post(
        expected_rasa_url,
        callback=mock_rasa_callbacks,
    )

    assert await rasa_callbacks.ask_to_join(
        'id_of_asker',
        'partner_id_to_ask',
    ) == external_intent_response

    assert mock_rasa_callbacks.mock_calls == [expected_rasa_call]


@pytest.mark.asyncio
async def test_join_room(
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> None:
    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'a_receiving_user',
        'EXTERNAL_join_room',
        {
            'partner_id': 'a_sending_user',
            'room_url': 'https://room-unittest/url',
        },
    )
    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=external_intent_response))
    mock_aioresponses.post(
        expected_rasa_url,
        callback=mock_rasa_callbacks,
    )

    assert await rasa_callbacks.join_room(
        'a_sending_user',
        'a_receiving_user',
        'https://room-unittest/url',
    ) == external_intent_response

    assert mock_rasa_callbacks.mock_calls == [expected_rasa_call]


@pytest.mark.asyncio
async def test_find_partner(
        rasa_callbacks_expected_call_builder: Callable[[Text, Text, Dict[Text, Any]], Tuple[Text, call]],
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> None:
    expected_rasa_url, expected_rasa_call = rasa_callbacks_expected_call_builder(
        'a_receiving_user',
        'EXTERNAL_find_partner',
        {},
    )
    mock_rasa_callbacks = AsyncMock(return_value=CallbackResult(payload=external_intent_response))
    mock_aioresponses.post(
        expected_rasa_url,
        callback=mock_rasa_callbacks,
    )

    assert await rasa_callbacks.find_partner(
        'some_sender_id',
        'a_receiving_user',
    ) == external_intent_response

    assert mock_rasa_callbacks.mock_calls == [expected_rasa_call]
