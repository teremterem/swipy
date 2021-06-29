import datetime
import logging
import os
from abc import ABC, abstractmethod
from distutils.util import strtobool
from pprint import pformat
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType, ReminderScheduled, UserUtteranceReverted
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import ACTION_LISTEN_NAME

from actions import daily_co
from actions import rasa_callbacks
from actions import telegram_helpers
from actions.rasa_callbacks import EXTERNAL_ASK_TO_JOIN_INTENT, EXTERNAL_ASK_TO_CONFIRM_INTENT
from actions.user_state_machine import UserStateMachine, UserState, NATIVE_UNKNOWN, PARTNER_CONFIRMATION_TIMEOUT_SEC
from actions.user_vault import UserVault, IUserVault
from actions.utils import stack_trace_to_str, datetime_now, get_intent_of_latest_message_reliably, SwiperError

logger = logging.getLogger(__name__)

TELL_USER_ABOUT_ERRORS = strtobool(os.getenv('TELL_USER_ABOUT_ERRORS', 'yes'))
SEND_ERROR_STACK_TRACE_TO_SLOT = strtobool(os.getenv('SEND_ERROR_STACK_TRACE_TO_SLOT', 'yes'))
FIND_PARTNER_FREQUENCY_SEC = float(os.getenv('FIND_PARTNER_FREQUENCY_SEC', '5'))
FIND_PARTNER_FOLLOWUP_DELAY_SEC = float(os.getenv('FIND_PARTNER_FOLLOWUP_DELAY_SEC', '2'))
GREETING_MAKES_USER_OK_TO_CHITCHAT = strtobool(os.getenv('GREETING_MAKES_USER_OK_TO_CHITCHAT', 'yes'))

SWIPER_STATE_SLOT = 'swiper_state'
SWIPER_ACTION_RESULT_SLOT = 'swiper_action_result'
SWIPER_NATIVE_SLOT = 'swiper_native'
DEEPLINK_DATA_SLOT = 'deeplink_data'
TELEGRAM_FROM_SLOT = 'telegram_from'

SWIPER_ERROR_SLOT = 'swiper_error'
SWIPER_ERROR_TRACE_SLOT = 'swiper_error_trace'

EXTERNAL_FIND_PARTNER_INTENT = 'EXTERNAL_find_partner'
EXTERNAL_EXPIRE_PARTNER_CONFIRMATION = 'EXTERNAL_expire_partner_confirmation'
ACTION_FIND_PARTNER = 'action_find_partner'
ACTION_ACCEPT_INVITATION = 'action_accept_invitation'


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
        logger.info('BEGIN ACTION RUN: %r (CURRENT USER ID = %r)', self.name(), tracker.sender_id)

        user_vault = UserVault()

        # noinspection PyBroadException
        try:
            metadata = tracker.latest_message.get('metadata') or {}
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('ActionRegisterMetadata - latest_message.metadata:\n%s', pformat(metadata))

            deeplink_data = metadata.get(DEEPLINK_DATA_SLOT)
            telegram_from = metadata.get(TELEGRAM_FROM_SLOT)

            current_user = user_vault.get_user(tracker.sender_id)

            if deeplink_data:
                current_user.deeplink_data = deeplink_data

                dl_entries = deeplink_data.split('_')
                for dl_entry in dl_entries:
                    dl_parts = dl_entry.split('-', maxsplit=1)
                    if len(dl_parts) > 1 and dl_parts[0] == 'n' and dl_parts[1]:
                        current_user.native = dl_parts[1]
                        break

            if telegram_from:
                current_user.telegram_from = telegram_from

                teleg_lang_code = telegram_from.get('language_code')
                if teleg_lang_code:
                    current_user.teleg_lang_code = teleg_lang_code

                    if current_user.native == NATIVE_UNKNOWN:
                        current_user.native = teleg_lang_code

            user_vault.save(current_user)

            events = list(await self.swipy_run(
                dispatcher,
                tracker,
                domain,
                current_user,
                user_vault,
            ))

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

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                'END ACTION RUN: %r (CURRENT USER ID = %r)\n\nRETURNED EVENTS:\n\n%s\n',
                self.name(),
                tracker.sender_id,
                pformat(events),
            )
        else:
            logger.info(
                'END ACTION RUN: %r (CURRENT USER ID = %r)',
                self.name(),
                tracker.sender_id,
            )
        return events


class ActionSessionStart(BaseSwiperAction):
    """Adaptation of https://github.com/RasaHQ/rasa/blob/main/rasa/core/actions/action.py ::ActionSessionStart"""

    def name(self) -> Text:
        return 'action_session_start'

    @staticmethod
    def _slot_set_events_from_tracker(tracker: Tracker) -> List[EventType]:
        return [
            SlotSet(key=slot_key, value=slot_value)
            for slot_key, slot_value in tracker.slots.items()
            if slot_key not in (
                SWIPER_STATE_SLOT,
                rasa_callbacks.PARTNER_ID_SLOT,
                SWIPER_ERROR_SLOT,
                SWIPER_ERROR_TRACE_SLOT,
            )
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
        return events

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        events = list(await super().run(dispatcher, tracker, domain))

        events.append(ActionExecuted(ACTION_LISTEN_NAME))

        return events


class ActionOfferChitchat(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_offer_chitchat'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        if GREETING_MAKES_USER_OK_TO_CHITCHAT:
            if current_user.state in (
                    UserState.NEW,
                    UserState.ASKED_TO_JOIN,  # TODO oleksandr: are you sure about this ?
                    UserState.ASKED_TO_CONFIRM,  # TODO oleksandr: are you sure about this ?
                    UserState.ROOMED,
                    UserState.REJECTED_JOIN,
                    UserState.REJECTED_CONFIRM,
                    UserState.DO_NOT_DISTURB,
            ):
                # noinspection PyUnresolvedReferences
                current_user.become_ok_to_chitchat()
                user_vault.save(current_user)

        latest_intent = tracker.get_intent_of_latest_message()
        if latest_intent == 'how_it_works':
            dispatcher.utter_message(response='utter_how_it_works')
        else:  # 'greet'
            dispatcher.utter_message(response='utter_greet_offer_chitchat')

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
            SlotSet(
                key=SWIPER_NATIVE_SLOT,
                value=current_user.native,
            ),
            SlotSet(
                key=DEEPLINK_DATA_SLOT,
                value=current_user.deeplink_data,
            ),
            SlotSet(
                key=TELEGRAM_FROM_SLOT,
                value=current_user.telegram_from,
            ),
        ]


class ActionFindPartner(BaseSwiperAction):
    def name(self) -> Text:
        return ACTION_FIND_PARTNER

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        latest_intent = get_intent_of_latest_message_reliably(tracker)
        triggered_by_reminder = latest_intent == EXTERNAL_FIND_PARTNER_INTENT

        if triggered_by_reminder:
            events = [
                # get rid of artificial intent so it doesn't interfere with story predictions
                UserUtteranceReverted(),
            ]

            if current_user.state not in [
                UserState.WANTS_CHITCHAT,
                UserState.OK_TO_CHITCHAT,
            ]:
                # the search was stopped for the user one way or another (user said stop, or was asked to join etc.)
                # => don't do any partner searching and don't schedule another reminder
                return events

        else:  # user just requested chitchat
            dispatcher.utter_message(response='utter_ok_arranging_chitchat')

            # noinspection PyUnresolvedReferences
            current_user.request_chitchat()
            user_vault.save(current_user)

            events = [
                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.SUCCESS,
                ),
            ]

        partner = user_vault.get_random_available_partner(current_user)

        if partner:
            user_profile_photo_id = telegram_helpers.get_user_profile_photo_file_id(current_user.user_id)

            await rasa_callbacks.ask_to_join(
                current_user.user_id,
                partner.user_id,
                user_profile_photo_id,
                suppress_callback_errors=True,
            )

            events.append(schedule_find_partner_reminder())

        return events


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

        latest_intent = get_intent_of_latest_message_reliably(tracker)

        if latest_intent == EXTERNAL_ASK_TO_JOIN_INTENT:
            response_template = 'utter_someone_wants_to_chat'
            # noinspection PyUnresolvedReferences
            current_user.become_asked_to_join(partner_id)
            user_vault.save(current_user)

        elif latest_intent == EXTERNAL_ASK_TO_CONFIRM_INTENT:
            response_template = 'utter_found_someone_check_ready'
            # noinspection PyUnresolvedReferences
            current_user.become_asked_to_confirm(partner_id)
            user_vault.save(current_user)

        else:
            raise SwiperError(
                f"{repr(self.name())} was triggered by an unexpected intent ({repr(latest_intent)}) - either "
                f"{repr(EXTERNAL_ASK_TO_JOIN_INTENT)} or {repr(EXTERNAL_ASK_TO_CONFIRM_INTENT)} was expected"
            )

        partner_photo_file_id = tracker.get_slot(rasa_callbacks.PARTNER_PHOTO_FILE_ID_SLOT)
        if partner_photo_file_id:
            response_template += '_photo'
            response_kwargs = {
                rasa_callbacks.PARTNER_PHOTO_FILE_ID_SLOT: partner_photo_file_id,
            }
        else:
            response_kwargs = {}

        dispatcher.utter_message(response=response_template, **response_kwargs)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionAcceptInvitation(BaseSwiperAction):
    def name(self) -> Text:
        return ACTION_ACCEPT_INVITATION

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        partner = user_vault.get_user(current_user.partner_id)

        if partner.is_waiting_to_be_confirmed_by(current_user.user_id):
            # current user was the one asked to confirm and they just did => create the room
            return await self.create_room(dispatcher, current_user, partner, user_vault)
        elif partner.chitchat_can_be_offered():
            # confirm with the partner before creating any rooms
            return await self.confirm_with_asker(dispatcher, current_user, partner, user_vault)
        else:
            # noinspection PyUnresolvedReferences
            current_user.request_chitchat()
            user_vault.save(current_user)

            dispatcher.utter_message(response='utter_partner_already_gone')

            return [
                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.PARTNER_NOT_WAITING_ANYMORE,
                ),
                schedule_find_partner_reminder(delta_sec=FIND_PARTNER_FOLLOWUP_DELAY_SEC),
            ]

    @staticmethod
    async def confirm_with_asker(
            dispatcher: CollectingDispatcher,
            current_user: UserStateMachine,
            partner: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(response='utter_checking_if_partner_ready_too')

        user_profile_photo_id = telegram_helpers.get_user_profile_photo_file_id(current_user.user_id)

        # noinspection PyBroadException
        try:
            await rasa_callbacks.ask_to_confirm(current_user.user_id, partner.user_id, user_profile_photo_id)
        except Exception:
            # noinspection PyUnresolvedReferences
            current_user.request_chitchat()
            user_vault.save(current_user)
            raise

        # noinspection PyUnresolvedReferences
        current_user.wait_for_partner_to_confirm(partner.user_id)
        user_vault.save(current_user)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.PARTNER_HAS_BEEN_ASKED,
            ),
            schedule_expire_partner_confirmation(),
        ]

    @staticmethod
    async def create_room(
            dispatcher: CollectingDispatcher,
            current_user: UserStateMachine,
            partner: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        created_room = await daily_co.create_room(current_user.user_id)
        room_url = created_room['url']

        # noinspection PyBroadException
        try:
            # put partner into the room as well
            await rasa_callbacks.join_room(current_user.user_id, partner.user_id, room_url)
        except Exception:
            # noinspection PyUnresolvedReferences
            current_user.request_chitchat()
            user_vault.save(current_user)
            raise

        dispatcher.utter_message(
            response='utter_room_url',
            **{
                rasa_callbacks.ROOM_URL_SLOT: room_url,
            },
        )

        # noinspection PyUnresolvedReferences
        current_user.join_room(partner.user_id)
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
        partner_id = tracker.get_slot(rasa_callbacks.PARTNER_ID_SLOT)
        # noinspection PyUnresolvedReferences
        current_user.join_room(partner_id)
        user_vault.save(current_user)

        dispatcher.utter_message(response='utter_partner_ready_room_url')

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
        # noinspection PyUnresolvedReferences
        current_user.become_do_not_disturb()
        user_vault.save(current_user)

        dispatcher.utter_message(response='utter_hope_to_see_you_later')

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionRejectInvitation(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_reject_invitation'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        # noinspection PyUnresolvedReferences
        current_user.reject()
        user_vault.save(current_user)

        dispatcher.utter_message(response='utter_declined')

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionExpirePartnerConfirmation(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_expire_partner_confirmation'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        if current_user.state != UserState.WAITING_PARTNER_CONFIRM:
            # user was not waiting for anybody's confirmation anymore anyway - do nothing and cover your tracks
            return [
                UserUtteranceReverted(),
            ]

        dispatcher.utter_message(response='utter_partner_already_gone')

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
            schedule_find_partner_reminder(delta_sec=FIND_PARTNER_FOLLOWUP_DELAY_SEC),
        ]


def schedule_find_partner_reminder(delta_sec: float = FIND_PARTNER_FREQUENCY_SEC) -> ReminderScheduled:
    return _reschedule_reminder(
        EXTERNAL_FIND_PARTNER_INTENT,
        delta_sec,
    )


def schedule_expire_partner_confirmation(delta_sec: float = PARTNER_CONFIRMATION_TIMEOUT_SEC) -> ReminderScheduled:
    return _reschedule_reminder(
        EXTERNAL_EXPIRE_PARTNER_CONFIRMATION,
        delta_sec,
    )


def _reschedule_reminder(
        intent_name: Text,
        delta_sec: float,
        kill_on_user_message: bool = False,
) -> ReminderScheduled:
    date = datetime_now() + datetime.timedelta(seconds=delta_sec)

    reminder = ReminderScheduled(
        intent_name,
        trigger_date_time=date,
        name=intent_name,  # ensures rescheduling of the existing reminder
        kill_on_user_message=kill_on_user_message,
    )
    return reminder
