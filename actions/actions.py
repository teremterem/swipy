from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.daily_co import create_room


class ActionCreateRoom(Action):

    def name(self) -> Text:
        return 'action_create_room'  # TODO oleksandr: git this action more relevant name

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        created_room = await create_room()
        dispatcher.utter_message(response='utter_video_link', room_link=created_room['url'])
        return []
