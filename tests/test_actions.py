from pprint import pprint

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions import actions


def test_action_hello_world(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict,
):
    action = actions.ActionHelloWorld()
    actual_events = action.run(dispatcher, tracker, domain)
    pprint(actual_events)
    # assert actual_events == expected_events
