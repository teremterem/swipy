from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions import actions


def test_action_create_room(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict,
):
    action = actions.ActionCreateRoom()

    assert action.name() == 'action_create_room'

    actual_events = action.run(dispatcher, tracker, domain)
    assert actual_events == []

    assert dispatcher.messages[0]['text'] == 'unit_test_user'
