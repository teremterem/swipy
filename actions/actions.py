import logging
import os
from abc import ABC, abstractmethod
from distutils.util import strtobool
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType
from rasa_sdk.executor import CollectingDispatcher

from actions import daily_co
from actions import rasa_callbacks
from actions.user_state_machine import UserStateMachine, UserState
from actions.user_vault import UserVault, IUserVault
from actions.utils import InvalidSwiperStateError, stack_trace_to_str

logger = logging.getLogger(__name__)

SEND_ERROR_STACK_TRACE_TO_SLOT = strtobool(os.getenv('SEND_ERROR_STACK_TRACE_TO_SLOT', 'yes'))

SWIPER_STATE_SLOT = 'swiper_state'
SWIPER_ACTION_RESULT_SLOT = 'swiper_action_result'

SWIPER_ERROR_SLOT = 'swiper_error'
SWIPER_ERROR_TRACE_SLOT = 'swiper_error_trace'


class SwiperActionResult:
    PARTNER_HAS_BEEN_ASKED = 'partner_has_been_asked'
    PARTNER_WAS_NOT_FOUND = 'partner_was_not_found'

    ERROR = 'error'


class BaseSwiperAction(Action, ABC):
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

        # noinspection PyBroadException
        try:
            events = list(await self.swipy_run(
                dispatcher,
                tracker,
                domain,
                user_vault.get_user(tracker.sender_id),
                user_vault,
            ))
            events.extend([
                SlotSet(
                    key=SWIPER_ERROR_SLOT,
                    value=None,
                ),
                SlotSet(
                    key=SWIPER_ERROR_TRACE_SLOT,
                    value=None,
                ),
            ])

        except Exception as e:
            logger.exception(self.name())
            events = [
                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.ERROR,
                ),
                SlotSet(
                    key=SWIPER_ERROR_SLOT,
                    value=repr(e),
                ),
            ]
            if SEND_ERROR_STACK_TRACE_TO_SLOT:
                events.append(SlotSet(
                    key=SWIPER_ERROR_TRACE_SLOT,
                    value=stack_trace_to_str(e),
                ))

        events.append(SlotSet(
            key=SWIPER_STATE_SLOT,
            value=user_vault.get_user(tracker.sender_id).state,  # invoke get_user once again (just in case)
        ))
        return events


class ActionSessionStart(BaseSwiperAction):
    """Adaptation of https://github.com/RasaHQ/rasa/blob/main/rasa/core/actions/action.py ::ActionSessionStart"""

    def name(self) -> Text:
        return 'action_session_start'

    @staticmethod
    def _slot_set_events_from_tracker(tracker: Tracker) -> List[EventType]:
        # TODO oleksandr: should I skip session_started_metadata slot ?
        #  (metadata seems to receive some kind of special treatment in Rasa Core version of the action)
        return [
            SlotSet(key=slot_key, value=slot_value)
            for slot_key, slot_value in tracker.slots.items()
            if slot_key != SWIPER_STATE_SLOT
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


class ActionFindPartner(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_find_partner'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        partner = user_vault.get_random_available_user(
            exclude_user_id=current_user.user_id,
            newbie=True,
        )
        if not partner:
            partner = user_vault.get_random_available_user(
                exclude_user_id=current_user.user_id,
                newbie=False,
            )

        if partner:
            if partner.state != UserState.OK_FOR_CHITCHAT:
                # noinspection PyUnresolvedReferences
                current_user.fail_to_find_partner()
                user_vault.save(current_user)

                raise InvalidSwiperStateError(
                    f"randomly chosen partner {repr(partner.user_id)} is in a wrong state: {repr(partner.state)}"
                )

            await rasa_callbacks.ask_partner(partner.user_id)

            # noinspection PyUnresolvedReferences
            current_user.ask_partner(partner.user_id)
            user_vault.save(current_user)

            return [
                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.PARTNER_HAS_BEEN_ASKED,
                ),
            ]

        # noinspection PyUnresolvedReferences
        current_user.fail_to_find_partner()
        user_vault.save(current_user)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.PARTNER_WAS_NOT_FOUND,
            ),
        ]


class ActionAskToJoin(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_ask_to_join'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        pass


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

        created_room = await daily_co.create_room()
        room_url = created_room['url']
        dispatcher.utter_message(response='utter_video_link', room_link=room_url)

        await rasa_callbacks.invite_chitchat_partner(chitchat_partner.user_id, room_url)

        current_user.newbie = False
        user_vault.save(current_user)

        return [
            SlotSet(key='room_link', value=room_url),
        ]
