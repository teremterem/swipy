from typing import Dict, Text, Any, Callable
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses, CallbackResult
from yarl import URL


@pytest.fixture
def external_intent_response() -> Dict[Text, Any]:
    return {
        "tracker": {
            "sender_id": "some_sender",
            "slots": {
                "session_started_metadata": None
            },
            "latest_message": {
                "intent": {
                    "name": "EXTERNAL_intent"
                },
                "entities": [],
                "text": "EXTERNAL: EXTERNAL_intent",
                "message_id": None,
                "metadata": {
                    "is_external": True
                }
            },
            "latest_event_time": 1621177678.252209,
            "followup_action": None,
            "paused": False,
            "events": [
                {
                    "event": "session_started",
                    "timestamp": 1621172521.7641437
                },
                {
                    "event": "action",
                    "timestamp": 1621172521.7641604,
                    "name": "action_listen",
                    "policy": None,
                    "confidence": None,
                    "action_text": None,
                    "hide_rule_turn": False
                },
                {
                    "event": "user",
                    "timestamp": 1621177678.0622308,
                    "metadata": {
                        "is_external": True
                    },
                    "text": "EXTERNAL: EXTERNAL_intent",
                    "parse_data": {
                        "intent": {
                            "name": "EXTERNAL_intent"
                        },
                        "entities": [],
                        "text": "EXTERNAL: EXTERNAL_intent",
                        "message_id": None,
                        "metadata": {
                            "is_external": True
                        }
                    },
                    "input_channel": "telegram",
                    "message_id": None
                },
                {
                    "event": "user_featurization",
                    "timestamp": 1621177678.074598,
                    "use_text_for_featurization": False
                },
                {
                    "event": "action",
                    "timestamp": 1621177678.0746088,
                    "name": "utter_greet_offer_chitchat",
                    "policy": "policy_2_RulePolicy",
                    "confidence": 1.0,
                    "action_text": None,
                    "hide_rule_turn": True
                },
                {
                    "event": "bot",
                    "timestamp": 1621177678.0746486,
                    "metadata": {
                        "utter_action": "utter_greet_offer_chitchat"
                    },
                    "text": "Hi, do you want to chitchat?",
                    "data": {
                        "elements": None,
                        "quick_replies": None,
                        "buttons": None,
                        "attachment": None,
                        "image": None,
                        "custom": None
                    }
                },
                {
                    "event": "action",
                    "timestamp": 1621177678.252209,
                    "name": "action_listen",
                    "policy": "policy_2_RulePolicy",
                    "confidence": 1.0,
                    "action_text": None,
                    "hide_rule_turn": True
                }
            ],
            "latest_input_channel": "telegram",
            "active_loop": {},
            "latest_action": {
                "action_name": "action_listen"
            },
            "latest_action_name": "action_listen"
        }
    }


@pytest.fixture
def patch_rasa_callbacks(
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> Callable[[Text, Text, Dict[Text, Any]], AsyncMock]:
    def _patch(expected_receiver_id: Text, expected_intent: Text, expected_entities: Dict[Text, Any]) -> AsyncMock:
        # noinspection HttpUrlsUsage
        expected_url = (
            f"http://rasa-unittest:5005/unittest-core/conversations/{expected_receiver_id}/trigger_intent"
            f"?output_channel=telegram&token=rasaunittesttoken"
        )

        def _rasa_callback(url: URL, json: Dict[Text, Any] = None, **_) -> CallbackResult:
            assert url == URL(expected_url)
            assert json == {
                'name': expected_intent,
                'entities': expected_entities,
            }
            return CallbackResult(payload=external_intent_response)

        _mock_rasa_callbacks = AsyncMock(side_effect=_rasa_callback)
        mock_aioresponses.post(
            expected_url,
            callback=_mock_rasa_callbacks,
        )

        return _mock_rasa_callbacks

    return _patch
