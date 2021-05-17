from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.daily_co import create_room
from actions.rasa_callbacks import invite_chitchat_partner
from actions.user_vault import user_vault


class ActionMakeUserAvailable(Action):
    def name(self) -> Text:
        return 'action_make_user_available'

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_vault.get_user(tracker.sender_id)
        return []


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
        room_url = created_room['url']
        dispatcher.utter_message(response='utter_video_link', room_link=room_url)

        await invite_chitchat_partner(chitchat_partner.user_id, room_url)
        return []
