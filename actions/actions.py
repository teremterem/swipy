from abc import ABC, abstractmethod
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType
from rasa_sdk.executor import CollectingDispatcher

from actions.daily_co import create_room
from actions.rasa_callbacks import invite_chitchat_partner
from actions.user_state_machine import UserStateMachine
from actions.user_vault import UserVault, IUserVault


class BaseSwiperAction(Action, ABC):
    SWIPER_STATE_SLOT = 'swiper_state'

    @abstractmethod
    def name(self) -> Text:
        raise NotImplementedError('An action must implement a name')

    @abstractmethod
    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        raise NotImplementedError('Swiper action must implement its swipy_run method')

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        user_vault = UserVault()

        events = list(await self.swipy_run(
            dispatcher,
            tracker,
            domain,
            user_vault.get_user(tracker.sender_id),
            user_vault,
        ))
        events.append(SlotSet(
            key=self.SWIPER_STATE_SLOT,
            value=user_vault.get_user(tracker.sender_id).state,  # invoke get_user once again (just in case)
        ))
        return events


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

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        events = [SessionStarted()]

        if domain['session_config']['carry_over_slots_to_new_session']:
            events.extend(self._slot_set_events_from_tracker(tracker))

        return events

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        events = list(await super().run(dispatcher, tracker, domain))

        events.append(ActionExecuted('action_listen'))

        return events


class ActionCreateRoomExperimental(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_create_room_experimental'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        chitchat_partner = user_vault.get_random_available_user(tracker.sender_id)

        created_room = await create_room()
        room_url = created_room['url']
        dispatcher.utter_message(response='utter_video_link', room_link=room_url)

        await invite_chitchat_partner(chitchat_partner.user_id, room_url)
        return [
            SlotSet(key='room_link', value=room_url),
        ]
