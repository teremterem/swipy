import pytest


@pytest.fixture
def external_intent_response():
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
