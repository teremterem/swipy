from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.daily_co import create_room
from actions.user_state_machine import user_vault


class ActionFindSomeone(Action):

    def name(self) -> Text:
        return 'action_find_someone'

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        chitchat_partner = user_vault.get_random_available_user(tracker.sender_id)
        created_room = await create_room()
        dispatcher.utter_message(response='utter_video_link', room_link=created_room['url'])
        return []
