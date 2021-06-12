import asyncio
import datetime
import logging
import os
import uuid
from abc import ABC, abstractmethod
from distutils.util import strtobool
from pprint import pformat
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType, UserUtteranceReverted, ReminderScheduled
from rasa_sdk.executor import CollectingDispatcher

from actions import daily_co
from actions import rasa_callbacks
from actions import telegram_helpers
from actions.user_state_machine import UserStateMachine, UserState
from actions.user_vault import UserVault, IUserVault
from actions.utils import InvalidSwiperStateError, stack_trace_to_str, datetime_now

logger = logging.getLogger(__name__)

TELL_USER_ABOUT_ERRORS = strtobool(os.getenv('TELL_USER_ABOUT_ERRORS', 'yes'))
SEND_ERROR_STACK_TRACE_TO_SLOT = strtobool(os.getenv('SEND_ERROR_STACK_TRACE_TO_SLOT', 'yes'))
TELEGRAM_MSG_LIMIT_SLEEP_SEC = float(os.getenv('TELEGRAM_MSG_LIMIT_SLEEP_SEC', '1.1'))
QUESTION_TIMEOUT_SEC = float(os.getenv('QUESTION_TIMEOUT_SEC', '120'))
GREETING_MAKES_USER_OK_TO_CHITCHAT = strtobool(os.getenv('GREETING_MAKES_USER_OK_TO_CHITCHAT', 'yes'))

SWIPER_STATE_SLOT = 'swiper_state'
SWIPER_ACTION_RESULT_SLOT = 'swiper_action_result'
DEEPLINK_DATA_SLOT = 'deeplink_data'
TELEGRAM_FROM_SLOT = 'telegram_from'

SWIPER_ERROR_SLOT = 'swiper_error'
SWIPER_ERROR_TRACE_SLOT = 'swiper_error_trace'

PARTNER_ID_TO_LET_GO_SLOT = 'partner_id_to_let_go'


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
            events = list(await self.swipy_run(
                dispatcher,
                tracker,
                domain,
                user_vault.get_user(tracker.sender_id),
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
        metadata = tracker.latest_message.get('metadata') or {}
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('ActionOfferChitchat - latest_message.metadata:\n%s', pformat(metadata))

        deeplink_data = metadata.get(DEEPLINK_DATA_SLOT)
        telegram_from = metadata.get(TELEGRAM_FROM_SLOT)

        save_current_user = False
        if GREETING_MAKES_USER_OK_TO_CHITCHAT:
            if current_user.state in (
                    UserState.NEW,
                    # UserState.WAITING_PARTNER_JOIN,
                    # UserState.WAITING_PARTNER_CONFIRM,
                    # UserState.ASKED_TO_JOIN,
                    # UserState.ASKED_TO_CONFIRM,
                    # UserState.ROOMED,
                    UserState.REJECTED_JOIN,  # TODO oleksandr: are you sure about this ?
                    UserState.REJECTED_CONFIRM,  # TODO oleksandr: are you sure about this ?
                    UserState.JOIN_TIMED_OUT,
                    UserState.CONFIRM_TIMED_OUT,
                    UserState.DO_NOT_DISTURB,
            ):
                # noinspection PyUnresolvedReferences
                current_user.become_ok_to_chitchat()
                save_current_user = True

        if deeplink_data:
            current_user.deeplink_data = deeplink_data

            dl_entries = deeplink_data.split('_')
            for dl_entry in dl_entries:
                dl_parts = dl_entry.split('-', maxsplit=1)
                if len(dl_parts) > 1 and dl_parts[0] == 'n':
                    current_user.native = dl_parts[1]

            save_current_user = True

        if telegram_from:
            current_user.telegram_from = telegram_from
            save_current_user = True

        if save_current_user:
            user_vault.save(current_user)

        latest_intent = tracker.get_intent_of_latest_message()
        if latest_intent == 'how_it_works':
            dispatcher.utter_message(response='utter_how_it_works')
        else:  # it is either 'greet' or 'start'
            dispatcher.utter_message(response='utter_greet_offer_chitchat')

        events = [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]
        if deeplink_data:
            events.append(SlotSet(
                key=DEEPLINK_DATA_SLOT,
                value=deeplink_data,
            ))
        if telegram_from:
            events.append(SlotSet(
                key=TELEGRAM_FROM_SLOT,
                value=telegram_from,
            ))
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
            if not partner.can_be_offered_chitchat():
                # noinspection PyUnresolvedReferences
                current_user.request_chitchat()
                user_vault.save(current_user)

                raise InvalidSwiperStateError(
                    f"randomly chosen partner {repr(partner.user_id)} is in a wrong state: {repr(partner.state)}"
                )

            # noinspection PyUnresolvedReferences
            current_user.request_chitchat()
            # noinspection PyUnresolvedReferences
            current_user.wait_for_partner(partner.user_id)
            user_vault.save(current_user)

            user_profile_photo_id = telegram_helpers.get_user_profile_photo_file_id(current_user.user_id)
            await rasa_callbacks.ask_to_join(current_user.user_id, partner.user_id, user_profile_photo_id)

            return [
                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.PARTNER_HAS_BEEN_ASKED,
                ),
            ]

        # noinspection PyUnresolvedReferences
        current_user.request_chitchat()
        user_vault.save(current_user)

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

        await rasa_callbacks.ask_to_join(current_user.user_id, partner.user_id, user_profile_photo_id)

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

        # put partner into the room as well
        await rasa_callbacks.join_room(current_user.user_id, partner.user_id, room_url)

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


async def let_partner_go_if_applicable(current_user: UserStateMachine, partner: UserStateMachine) -> None:
    if partner.partner_id == current_user.user_id:
        if partner.state == UserState.WAITING_PARTNER_JOIN:
            # force the original sender of the declined invitation to "move along" in their partner search
            await rasa_callbacks.find_partner(current_user.user_id, partner.user_id)
        elif partner.state == UserState.WAITING_PARTNER_CONFIRM:
            await rasa_callbacks.report_unavailable(current_user.user_id, partner.user_id)


class ActionDoNotDisturb(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_do_not_disturb'

    def update_current_user(self, current_user: UserStateMachine):
        # noinspection PyUnresolvedReferences
        current_user.become_do_not_disturb()

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        initial_partner_id = current_user.partner_id

        self.update_current_user(current_user)
        user_vault.save(current_user)

        if initial_partner_id:
            partner = user_vault.get_user(initial_partner_id)
            await let_partner_go_if_applicable(current_user, partner)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionRejectInvitation(ActionDoNotDisturb):
    def name(self) -> Text:
        return 'action_reject_invitation'

    def update_current_user(self, current_user: UserStateMachine):
        # noinspection PyUnresolvedReferences
        current_user.reject()


class ActionLetPartnerGo(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_let_partner_go'

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        partner_id_to_let_go = tracker.get_slot(PARTNER_ID_TO_LET_GO_SLOT)

        if partner_id_to_let_go:
            partner_to_let_go = user_vault.get_user(partner_id_to_let_go)
            await let_partner_go_if_applicable(current_user, partner_to_let_go)

            if current_user.state in (
                    UserState.ASKED_TO_JOIN,
                    UserState.ASKED_TO_CONFIRM
            ) and current_user.partner_id == partner_id_to_let_go:
                # noinspection PyUnresolvedReferences
                current_user.time_out()
                user_vault.save(current_user)

        return [UserUtteranceReverted()]
