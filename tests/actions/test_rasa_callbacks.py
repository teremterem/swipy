from typing import Dict, Text, Any
from unittest.mock import MagicMock

import pytest
from aioresponses import aioresponses, CallbackResult

from actions.rasa_callbacks import invite_chitchat_partner


@pytest.mark.asyncio
async def test_invite_chitchat_partner(
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> None:
    def rasa_core_callback(url, json=None, **kwargs):
        assert json == {
            'name': 'EXTERNAL_invite_chitchat_partner',
            'entities': {
                'room_link': 'https://room-unittest/url',
            },
        }
        return CallbackResult(payload=external_intent_response)

    rasa_core_callback_mock = MagicMock(side_effect=rasa_core_callback)
    # noinspection HttpUrlsUsage
    mock_aioresponses.post(
        'http://rasa-unittest:5005/core/conversations/a_partner_id/trigger_intent'
        '?output_channel=latest&token=rasaunittesttoken',
        callback=rasa_core_callback_mock,
    )

    await invite_chitchat_partner('a_partner_id', 'https://room-unittest/url')
    rasa_core_callback_mock.assert_called_once()
