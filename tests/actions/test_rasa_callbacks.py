from typing import Dict, Text, Any
from unittest.mock import MagicMock

import pytest
from aioresponses import aioresponses, CallbackResult

from actions import rasa_callbacks


@pytest.mark.asyncio
async def test_ask_to_join(
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> None:
    def rasa_core_callback(url, json=None, **kwargs):
        assert json == {
            'name': 'EXTERNAL_ask_to_join',
            'entities': {
                'partner_id': 'id_of_asker',
            },
        }
        return CallbackResult(payload=external_intent_response)

    mock_rasa_core_callback = MagicMock(side_effect=rasa_core_callback)
    # noinspection HttpUrlsUsage
    mock_aioresponses.post(
        'http://rasa-unittest:5005/unittest-core/conversations/partner_id_to_ask/trigger_intent'
        '?output_channel=telegram&token=rasaunittesttoken',
        callback=mock_rasa_core_callback,
    )

    await rasa_callbacks.ask_to_join('id_of_asker', 'partner_id_to_ask')
    mock_rasa_core_callback.assert_called_once()


@pytest.mark.asyncio
async def test_join_room(
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> None:
    def rasa_core_callback(url, json=None, **kwargs):
        assert json == {
            'name': 'EXTERNAL_join_room',
            'entities': {
                'partner_id': 'a_sending_user',
                'room_url': 'https://room-unittest/url',
            },
        }
        return CallbackResult(payload=external_intent_response)

    mock_rasa_core_callback = MagicMock(side_effect=rasa_core_callback)
    # noinspection HttpUrlsUsage
    mock_aioresponses.post(
        'http://rasa-unittest:5005/unittest-core/conversations/a_receiving_user/trigger_intent'
        '?output_channel=telegram&token=rasaunittesttoken',
        callback=mock_rasa_core_callback,
    )

    await rasa_callbacks.join_room('a_sending_user', 'a_receiving_user', 'https://room-unittest/url')
    mock_rasa_core_callback.assert_called_once()


@pytest.mark.asyncio
async def test_find_partner(
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> None:
    def rasa_core_callback(url, json=None, **kwargs):
        assert json == {
            'name': 'EXTERNAL_find_partner',
            'entities': {},
        }
        return CallbackResult(payload=external_intent_response)

    mock_rasa_core_callback = MagicMock(side_effect=rasa_core_callback)
    # noinspection HttpUrlsUsage
    mock_aioresponses.post(
        'http://rasa-unittest:5005/unittest-core/conversations/a_receiving_user/trigger_intent'
        '?output_channel=telegram&token=rasaunittesttoken',
        callback=mock_rasa_core_callback,
    )

    await rasa_callbacks.find_partner('some_sender_id', 'a_receiving_user')
    mock_rasa_core_callback.assert_called_once()
