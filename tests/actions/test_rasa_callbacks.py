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

    rasa_core_callback_mock = MagicMock(side_effect=rasa_core_callback)
    # noinspection HttpUrlsUsage
    mock_aioresponses.post(
        'http://rasa-unittest:5005/unittest-core/conversations/partner_id_to_ask/trigger_intent'
        '?output_channel=telegram&token=rasaunittesttoken',
        callback=rasa_core_callback_mock,
    )

    await rasa_callbacks.ask_to_join('partner_id_to_ask', 'id_of_asker')
    rasa_core_callback_mock.assert_called_once()


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

    rasa_core_callback_mock = MagicMock(side_effect=rasa_core_callback)
    # noinspection HttpUrlsUsage
    mock_aioresponses.post(
        'http://rasa-unittest:5005/unittest-core/conversations/a_receiving_user/trigger_intent'
        '?output_channel=telegram&token=rasaunittesttoken',
        callback=rasa_core_callback_mock,
    )

    await rasa_callbacks.join_room('a_receiving_user', 'a_sending_user', 'https://room-unittest/url')
    rasa_core_callback_mock.assert_called_once()


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

    rasa_core_callback_mock = MagicMock(side_effect=rasa_core_callback)
    # noinspection HttpUrlsUsage
    mock_aioresponses.post(
        'http://rasa-unittest:5005/unittest-core/conversations/a_receiving_user/trigger_intent'
        '?output_channel=telegram&token=rasaunittesttoken',
        callback=rasa_core_callback_mock,
    )

    await rasa_callbacks.find_partner('a_receiving_user')
    rasa_core_callback_mock.assert_called_once()
