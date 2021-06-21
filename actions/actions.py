import datetime
import logging
import os
import uuid
from abc import ABC, abstractmethod
from distutils.util import strtobool
from pprint import pformat
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType, ReminderScheduled, FollowupAction, \
    UserUtteranceReverted
from rasa_sdk.executor import CollectingDispatcher

from actions import daily_co
from actions import rasa_callbacks
from actions import telegram_helpers
from actions.user_state_machine import UserStateMachine, UserState, NATIVE_UNKNOWN
from actions.user_vault import UserVault, IUserVault
from actions.utils import InvalidSwiperStateError, stack_trace_to_str, datetime_now

logger = logging.getLogger(__name__)

TELL_USER_ABOUT_ERRORS = strtobool(os.getenv('TELL_USER_ABOUT_ERRORS', 'yes'))
SEND_ERROR_STACK_TRACE_TO_SLOT = strtobool(os.getenv('SEND_ERROR_STACK_TRACE_TO_SLOT', 'yes'))
FIND_PARTNER_FREQUENCY_SEC = float(os.getenv('FIND_PARTNER_FREQUENCY_SEC', '10'))
QUESTION_TIMEOUT_SEC = float(os.getenv('QUESTION_TIMEOUT_SEC', '120'))
GREETING_MAKES_USER_OK_TO_CHITCHAT = strtobool(os.getenv('GREETING_MAKES_USER_OK_TO_CHITCHAT', 'yes'))

SWIPER_STATE_SLOT = 'swiper_state'
SWIPER_ACTION_RESULT_SLOT = 'swiper_action_result'
SWIPER_NATIVE_SLOT = 'swiper_native'
DEEPLINK_DATA_SLOT = 'deeplink_data'
TELEGRAM_FROM_SLOT = 'telegram_from'

SWIPER_ERROR_SLOT = 'swiper_error'
SWIPER_ERROR_TRACE_SLOT = 'swiper_error_trace'

PARTNER_ID_TO_LET_GO_SLOT = 'partner_id_to_let_go'

EXTERNAL_FIND_PARTNER_INTENT = 'EXTERNAL_find_partner'


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

        logger.info('END ACTION RUN: %r (CURRENT USER ID = %r)', self.name(), tracker.sender_id)
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

        events.append(ActionExecuted('action_listen'))

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
        return 'action_find_partner'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        # tracker.get_intent_of_latest_message() doesn't work for artificial messages because intent_ranking is absent
        triggered_by_reminder = (
                tracker.latest_message and
                (tracker.latest_message.get('intent') or {}).get('name') == EXTERNAL_FIND_PARTNER_INTENT
        )  # TODO oleksandr: extract part of this expression to utils.py::get_intent_of_latest_message_reliably() ?

        if triggered_by_reminder:
            if current_user.state != UserState.WANTS_CHITCHAT:
                # the search was stopped for the user one way or another (user said stop, or was asked to join etc.)
                # => don't do any partner searching and don't schedule another reminder
                return [
                    # get rid of artificial intent so it doesn't interfere with story predictions
                    UserUtteranceReverted(),
                ]
        else:  # user just requested chitchat
            # noinspection PyUnresolvedReferences
            current_user.request_chitchat()
            user_vault.save(current_user)

        partner = user_vault.get_random_available_partner(current_user)

        if partner:
            user_profile_photo_id = telegram_helpers.get_user_profile_photo_file_id(current_user.user_id)

            await rasa_callbacks.ask_to_join(
                current_user.user_id,
                partner.user_id,
                user_profile_photo_id,
                suppress_callback_errors=True,
            )

            date = datetime_now() + datetime.timedelta(seconds=FIND_PARTNER_FREQUENCY_SEC)

            events = [
                ReminderScheduled(
                    EXTERNAL_FIND_PARTNER_INTENT,
                    trigger_date_time=date,
                    name=EXTERNAL_FIND_PARTNER_INTENT,
                    kill_on_user_message=False,
                ),
            ]
            if triggered_by_reminder:
                # get rid of artificial intent so it doesn't interfere with story predictions
                events.append(UserUtteranceReverted())
            else:
                events.append(SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.SUCCESS,
                ))
            return events

        dispatcher.utter_message(response='utter_no_one_was_found')

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
        current_user.become_asked(partner_id)
        user_vault.save(current_user)

        if current_user.state == UserState.ASKED_TO_CONFIRM:
            response_template = 'utter_found_someone_check_ready'
        else:  # current_user.state == UserState.ASKED_TO_JOIN
            response_template = 'utter_someone_wants_to_chat'

        partner_photo_file_id = tracker.get_slot(rasa_callbacks.PARTNER_PHOTO_FILE_ID_SLOT)
        if partner_photo_file_id:
            response_template += '_photo'
            response_kwargs = {
                rasa_callbacks.PARTNER_PHOTO_FILE_ID_SLOT: partner_photo_file_id,
            }
        else:
            response_kwargs = {}

        dispatcher.utter_message(response=response_template, **response_kwargs)

        date = datetime_now() + datetime.timedelta(seconds=QUESTION_TIMEOUT_SEC)

        reminder = ReminderScheduled(
            'EXTERNAL_let_partner_go',
            trigger_date_time=date,
            entities={
                PARTNER_ID_TO_LET_GO_SLOT: partner_id,
            },
            name=str(uuid.uuid4()),
            kill_on_user_message=False,
        )
        return [
            reminder,
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
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
        partner = user_vault.get_user(current_user.partner_id)
        if not partner.is_waiting_for(current_user.user_id):
            # noinspection PyUnresolvedReferences
            current_user.request_chitchat()
            user_vault.save(current_user)

            dispatcher.utter_message(response='utter_partner_already_gone')

            return [
                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.PARTNER_NOT_WAITING_ANYMORE,
                ),
                FollowupAction('action_find_partner'),
            ]

        if current_user.state == UserState.ASKED_TO_JOIN:
            # instead of creating a room, first confirm with the partner
            return await self.confirm_with_asker(dispatcher, current_user, partner, user_vault)

        elif current_user.state == UserState.ASKED_TO_CONFIRM:
            return await self.create_room(dispatcher, current_user, partner, user_vault)

        else:  # invalid state
            raise InvalidSwiperStateError(
                f"Room cannot be created because current user {repr(current_user.user_id)} "
                f"is in invalid state: {repr(current_user.state)}"
            )

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
            await rasa_callbacks.ask_to_join(current_user.user_id, partner.user_id, user_profile_photo_id)
        except Exception:
            # noinspection PyUnresolvedReferences
            current_user.request_chitchat()
            user_vault.save(current_user)
            raise

        # noinspection PyUnresolvedReferences
        current_user.wait_for_partner(partner.user_id)
        user_vault.save(current_user)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.PARTNER_HAS_BEEN_ASKED,
            ),
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

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionRequestChitchat(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_request_chitchat'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        # noinspection PyUnresolvedReferences
        current_user.request_chitchat()
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
        # noinspection PyUnresolvedReferences
        current_user.become_do_not_disturb()
        user_vault.save(current_user)

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

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]
