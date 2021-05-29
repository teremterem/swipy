import asyncio
import datetime
import logging
import os
from abc import ABC, abstractmethod
from distutils.util import strtobool
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType, ReminderScheduled, UserUtteranceReverted
from rasa_sdk.executor import CollectingDispatcher

from actions import daily_co
from actions import rasa_callbacks
from actions.user_state_machine import UserStateMachine, UserState
from actions.user_vault import UserVault, IUserVault
from actions.utils import InvalidSwiperStateError, stack_trace_to_str, current_timestamp_int

logger = logging.getLogger(__name__)

TELL_USER_ABOUT_ERRORS = strtobool(os.getenv('TELL_USER_ABOUT_ERRORS', 'yes'))
SEND_ERROR_STACK_TRACE_TO_SLOT = strtobool(os.getenv('SEND_ERROR_STACK_TRACE_TO_SLOT', 'yes'))
TELEGRAM_MSG_LIMIT_SLEEP_SEC = float(os.getenv('TELEGRAM_MSG_LIMIT_SLEEP_SEC', '1.1'))
QUESTION_TIMEOUT_SEC = float(os.getenv('QUESTION_TIMEOUT_SEC', '120'))

SWIPER_STATE_SLOT = 'swiper_state'
SWIPER_ACTION_RESULT_SLOT = 'swiper_action_result'

SWIPER_ERROR_SLOT = 'swiper_error'
SWIPER_ERROR_TRACE_SLOT = 'swiper_error_trace'


class SwiperActionResult:
    PARTNER_HAS_BEEN_ASKED = 'partner_has_been_asked'
    PARTNER_WAS_NOT_FOUND = 'partner_was_not_found'
    PARTNER_NOT_WAITING_ANYMORE = 'partner_not_waiting_anymore'
    ROOM_URL_READY = 'room_url_ready'

    SUCCESS = 'success'
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
        logger.info('BEGIN ACTION RUN: %s (CURRENT USER ID = %r)', self.name(), tracker.sender_id)

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
            # noinspection PyBroadException
            try:
                if TELL_USER_ABOUT_ERRORS:
                    dispatcher.utter_message(response='utter_error')
            except Exception:
                logger.exception('%s (less important error)', self.name())

        current_user = user_vault.get_user(tracker.sender_id)  # invoke get_user once again (just in case)
        events.extend([
            SlotSet(
                key=SWIPER_STATE_SLOT,
                value=current_user.state,
            ),
            SlotSet(
                key=rasa_callbacks.PARTNER_ID_SLOT,
                value=current_user.partner_id,
            ),
        ])

        logger.info('END ACTION RUN: %s (CURRENT USER ID = %r)', self.name(), tracker.sender_id)
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
            if slot_key not in [
                SWIPER_STATE_SLOT,
                rasa_callbacks.PARTNER_ID_SLOT,
            ]
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
        # sleep for a second to avoid hitting a weird telegram message limit that (I still don't know why,
        # but it happens when this action is invoked externally by someone who rejected invitation)
        await asyncio.sleep(TELEGRAM_MSG_LIMIT_SLEEP_SEC)

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
            if partner.state != UserState.OK_TO_CHITCHAT:
                # noinspection PyUnresolvedReferences
                current_user.become_ok_to_chitchat()
                user_vault.save(current_user)

                raise InvalidSwiperStateError(
                    f"randomly chosen partner {repr(partner.user_id)} is in a wrong state: {repr(partner.state)}"
                )

            await rasa_callbacks.ask_to_join(current_user.user_id, partner.user_id)

            # noinspection PyUnresolvedReferences
            current_user.ask_partner(partner.user_id)
            user_vault.save(current_user)

            return [
                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.PARTNER_HAS_BEEN_ASKED,
                ),
            ]

        dispatcher.utter_message(response='utter_no_one_was_found')

        # noinspection PyUnresolvedReferences
        current_user.become_ok_to_chitchat()
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
        partner_id = tracker.get_slot(rasa_callbacks.PARTNER_ID_SLOT)
        # noinspection PyUnresolvedReferences
        current_user.become_asked_to_join(partner_id)
        user_vault.save(current_user)

        date = datetime.datetime.now() + datetime.timedelta(seconds=QUESTION_TIMEOUT_SEC)

        # TODO TODO TODO oleksandr: send partner_id as an entity !
        reminder = ReminderScheduled(
            "EXTERNAL_do_not_disturb",
            trigger_date_time=date,
            name="my_reminder",  # TODO TODO TODO oleksandr: use guid as a name !
            kill_on_user_message=False,
        )
        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
            reminder,
        ]


class ActionCreateRoom(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_create_room'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        # TODO TODO TODO oleksandr: cancel reminder !!!

        if current_user.partner_id is None:
            raise InvalidSwiperStateError(
                f"current user {repr(current_user.user_id)} cannot join the room "
                f"because current_user.partner_id is None",
            )

        partner = user_vault.get_user(current_user.partner_id)
        if partner.state != UserState.WAITING_PARTNER_ANSWER or partner.partner_id != current_user.user_id:
            # noinspection PyUnresolvedReferences
            current_user.become_ok_to_chitchat()
            user_vault.save(current_user)

            dispatcher.utter_message(response='utter_partner_already_gone')

            return [
                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.PARTNER_NOT_WAITING_ANYMORE,
                ),
            ]

        if current_timestamp_int() - partner.state_timestamp > QUESTION_TIMEOUT_SEC:
            dispatcher.utter_message(response='utter_checking_if_partner_ready_too')

            await rasa_callbacks.ask_if_ready(current_user.user_id, partner.user_id)

            # noinspection PyUnresolvedReferences
            current_user.ask_partner(partner.user_id)
            user_vault.save(current_user)

            return [
                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.PARTNER_HAS_BEEN_ASKED,
                ),
            ]

        created_room = await daily_co.create_room(current_user.user_id)
        room_url = created_room['url']

        # put partner into the room as well
        await rasa_callbacks.join_room(current_user.user_id, current_user.partner_id, room_url)

        dispatcher.utter_message(
            response='utter_room_url',
            **{
                rasa_callbacks.ROOM_URL_SLOT: room_url,
            },
        )

        # noinspection PyUnresolvedReferences
        current_user.join_room()
        user_vault.save(current_user)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.ROOM_URL_READY,
            ),
            SlotSet(
                key=rasa_callbacks.ROOM_URL_SLOT,
                value=room_url,
            ),
        ]


class ActionJoinRoom(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_join_room'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        # 'room_url' slot is expected to be set by the external caller
        dispatcher.utter_message(response='utter_found_partner_room_url')

        # noinspection PyUnresolvedReferences
        current_user.join_room()
        user_vault.save(current_user)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionBecomeOkToChitchat(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_become_ok_to_chitchat'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(response='utter_thanks_for_being_ok_to_chitchat')

        # noinspection PyUnresolvedReferences
        current_user.become_ok_to_chitchat()
        user_vault.save(current_user)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionDoNotDisturb(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_do_not_disturb'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        # TODO TODO TODO oleksandr: cancel reminder !!!

        initial_partner_id = current_user.partner_id

        # noinspection PyUnresolvedReferences
        current_user.become_do_not_disturb()
        user_vault.save(current_user)

        # TODO TODO TODO oleksandr: partner id was null once !!!
        partner = user_vault.get_user(initial_partner_id)
        # TODO oleksandr: reuse this condition (it is also present in ActionCreateRoom)
        if partner.state == UserState.WAITING_PARTNER_ANSWER and partner.partner_id == current_user.user_id:
            # force the original sender of the declined invitation to "move along" in their partner search
            await rasa_callbacks.find_partner(current_user.user_id, partner.user_id)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
            UserUtteranceReverted(),
        ]
