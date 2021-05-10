import os
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

DAILY_CO_TOKEN = os.environ['DAILY_CO_TOKEN']


class ActionCreateRoom(Action):

    def name(self) -> Text:
        return 'action_create_room'

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # dispatcher.utter_message(text=str(tracker.sender_id))
        dispatcher.utter_template('utter_video_link', tracker, room_link='https://roomlink')

        return []
