from abc import ABC, abstractmethod
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType
from rasa_sdk.executor import CollectingDispatcher

from actions.daily_co import create_room
from actions.rasa_callbacks import invite_chitchat_partner
from actions.user_vault import UserVault


class BaseSwiperAction(Action, ABC):
    SWIPER_STATE_SLOT = 'swiper_state'

    @abstractmethod
    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        raise NotImplementedError()

    def __init__(self):
        self.user_vault = UserVault()

    def get_current_user(self, tracker: Tracker):
        return self.user_vault.get_user(tracker.sender_id)


class ActionSessionStart(BaseSwiperAction):
    """Adaptation of https://github.com/RasaHQ/rasa/blob/main/rasa/core/actions/action.py ::ActionSessionStart"""

    def name(self) -> Text:
        return 'action_session_start'

    @classmethod
    def _slot_set_events_from_tracker(cls, tracker: Tracker) -> List[EventType]:
        # TODO oleksandr: should I skip session_started_metadata slot ?
        #  (metadata seems to receive some kind of special treatment in Rasa Core version of the action)
        return [
            SlotSet(key=slot_key, value=slot_value)
            for slot_key, slot_value in tracker.slots.items()
            if slot_key != cls.SWIPER_STATE_SLOT
        ]

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        """Runs action. Please see parent class for the full docstring."""
        _events = [SessionStarted()]

        if domain['session_config']['carry_over_slots_to_new_session']:
            _events.extend(self._slot_set_events_from_tracker(tracker))

        _events.append(SlotSet(key=self.SWIPER_STATE_SLOT, value=self.get_current_user(tracker).state))
        _events.append(ActionExecuted('action_listen'))

        return _events


class ActionMakeUserAvailable(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_make_user_available'

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        self.get_current_user(tracker)
        return []


class ActionFindSomeone(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_find_someone'

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        chitchat_partner = self.user_vault.get_random_available_user(tracker.sender_id)

        created_room = await create_room()
        room_url = created_room['url']
        dispatcher.utter_message(response='utter_video_link', room_link=room_url)

        await invite_chitchat_partner(chitchat_partner.user_id, room_url)
        return []
