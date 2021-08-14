import datetime
import logging
import os
from abc import ABC, abstractmethod
from distutils.util import strtobool
from pprint import pformat
from typing import Any, Text, Dict, List, Optional, Union

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType, ReminderScheduled, \
    UserUtteranceReverted, FollowupAction, ActionReverted
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import ACTION_LISTEN_NAME

from actions import daily_co
from actions import rasa_callbacks
from actions import telegram_helpers
from actions.rasa_callbacks import EXTERNAL_ASK_TO_JOIN_INTENT, EXTERNAL_ASK_TO_CONFIRM_INTENT
from actions.user_state_machine import UserStateMachine, UserState, NATIVE_UNKNOWN, PARTNER_CONFIRMATION_TIMEOUT_SEC, \
    SHORT_BREAK_TIMEOUT_SEC
from actions.user_vault import UserVault, IUserVault
from actions.utils import stack_trace_to_str, datetime_now, get_intent_of_latest_message_reliably, SwiperError, \
    current_timestamp_int, SwiperRasaCallbackError, present_partner_name

logger = logging.getLogger(__name__)

TELL_USER_ABOUT_ERRORS = strtobool(os.getenv('TELL_USER_ABOUT_ERRORS', 'yes'))
SEND_ERROR_STACK_TRACE_TO_SLOT = strtobool(os.getenv('SEND_ERROR_STACK_TRACE_TO_SLOT', 'yes'))
CLEAR_REJECTED_LIST_WHEN_NO_ONE_FOUND = strtobool(os.getenv('CLEAR_REJECTED_LIST_WHEN_NO_ONE_FOUND', 'yes'))
FIND_PARTNER_FREQUENCY_SEC = float(os.getenv('FIND_PARTNER_FREQUENCY_SEC', '5'))
PARTNER_SEARCH_TIMEOUT_SEC = int(os.getenv('PARTNER_SEARCH_TIMEOUT_SEC', '114'))  # 1 minute 54 seconds
ROOM_DISPOSAL_REPORT_DELAY_SEC = int(os.getenv('ROOM_DISPOSAL_REPORT_DELAY_SEC', '60'))  # 1 minute
GREETING_MAKES_USER_OK_TO_CHITCHAT = strtobool(os.getenv('GREETING_MAKES_USER_OK_TO_CHITCHAT', 'no'))
SEARCH_CANCELLATION_TAKES_A_BREAK = strtobool(os.getenv('SEARCH_CANCELLATION_TAKES_A_BREAK', 'no'))
WAITING_CANCELLATION_REJECTS_INVITATION = strtobool(os.getenv('WAITING_CANCELLATION_REJECTS_INVITATION', 'no'))

SWIPER_STATE_SLOT = 'swiper_state'
SWIPER_ACTION_RESULT_SLOT = 'swiper_action_result'
DEEPLINK_DATA_SLOT = 'deeplink_data'
TELEGRAM_FROM_SLOT = 'telegram_from'

SWIPER_ERROR_SLOT = 'swiper_error'
SWIPER_ERROR_TRACE_SLOT = 'swiper_error_trace'

PARTNER_SEARCH_START_TS_SLOT = 'partner_search_start_ts'
FEEDBACK_TEXT_SLOT = 'feedback_text'

VIDEOCHAT_INTENT = 'videochat'
SOMEONE_ELSE_INTENT = 'someone_else'
EXTERNAL_FIND_PARTNER_INTENT = 'EXTERNAL_find_partner'
EXTERNAL_EXPIRE_PARTNER_CONFIRMATION_INTENT = 'EXTERNAL_expire_partner_confirmation'
EXTERNAL_ROOM_DISPOSAL_REPORT_INTENT = 'EXTERNAL_room_disposal_report'
EXTERNAL_ROOM_EXPIRATION_REPORT_INTENT = 'EXTERNAL_room_expiration_report'

ACTION_DEFAULT_FALLBACK_NAME = 'action_default_fallback'
ACTION_SESSION_START_NAME = 'action_session_start'
ACTION_FIND_PARTNER_NAME = 'action_find_partner'
ACTION_ASK_TO_JOIN_NAME = 'action_ask_to_join'
ACTION_ACCEPT_INVITATION_NAME = 'action_accept_invitation'
ACTION_JOIN_ROOM_NAME = 'action_join_room'


class SwiperActionResult:
    USER_HAS_BEEN_ASKED = 'user_has_been_asked'
    PARTNER_HAS_BEEN_ASKED = 'partner_has_been_asked'
    PARTNER_WAS_NOT_FOUND = 'partner_was_not_found'
    PARTNER_NOT_WAITING_ANYMORE = 'partner_not_waiting_anymore'
    ROOM_URL_READY = 'room_url_ready'

    SUCCESS = 'success'
    ERROR = 'error'


UTTER_INVITATION_DECLINED = 'Ok, declined ❌\n'
UTTER_OK_LOOKING_FOR_PARTNER_TEMPLATE = 'utter_ok_looking_for_partner'

REMOVE_KEYBOARD_MARKUP = '{"remove_keyboard":true}'
RESTART_COMMAND_MARKUP = (
    '{"keyboard":['

    '[{"text":"/restart"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
CANCEL_MARKUP = (
    '{"keyboard":['

    '[{"text":"❌ Cancel"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
STOP_THE_CALL_MARKUP = (
    '{"keyboard":['

    '[{"text":"❌ Stop the call"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
YES_NO_SOMEONE_ELSE_MARKUP = (
    '{"keyboard":['

    '[{"text":"✅ Yes"},{"text":"❌ Not now"}],'
    '[{"text":"👤 Someone else"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
SOMEONE_ELSE_NO_MARKUP = (
    '{"keyboard":['

    '[{"text":"👤 Someone else"}],'
    '[{"text":"❌ No, thanks"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
YES_NO_MARKUP = (
    '{"keyboard":['

    '[{"text":"Yes"}],'
    '[{"text":"No"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
YES_CONNECT_HOW_DOES_IT_WORK_NO_THANKS_MARKUP = (
    '{"keyboard":['

    '[{"text":"✅ Yes, connect me"}],'
    '[{"text":"💡 How does it work?"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
YES_CONNECT_NO_THANKS_MARKUP = (
    '{"keyboard":['

    '[{"text":"✅ Yes, connect me"}],'
    '[{"text":"❌ No, thanks"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
SHARE_MY_CONTACT_CALL_ANOTHER_PERSON_MARKUP = (
    '{"keyboard":['

    '[{"text":"🤵 Share my username"}],'
    '[{"text":"♻️ Call another person"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
CALL_ANOTHER_PERSON_MARKUP = (
    '{"keyboard":['

    '[{"text":"♻️ Call another person"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)


class BaseSwiperAction(Action, ABC):
    @abstractmethod
    def name(self) -> Text:
        raise NotImplementedError('An action must implement a name')

    @abstractmethod
    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        raise NotImplementedError('Each action should be explicit on whether to update user activity timestamp or not')

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
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                'BEGIN ACTION RUN: %r (CURRENT USER ID = %r)\n\nTRACKER.EVENTS:\n\n%s\n',
                self.name(),
                tracker.sender_id,
                pformat(tracker.events),
            )
        else:
            logger.info(
                'BEGIN ACTION RUN: %r (CURRENT USER ID = %r)',
                self.name(),
                tracker.sender_id,
            )

        user_vault = UserVault()

        # noinspection PyBroadException
        try:
            metadata = tracker.latest_message.get('metadata') or {}
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('tracker.latest_message.metadata:\n%s', pformat(metadata))

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

            if self.should_update_user_activity_timestamp(tracker):
                current_user.update_activity_timestamp()

            current_user.save()

            if current_user.state == UserState.USER_BANNED:
                logger.info('IGNORING BANNED USER (ID = %r)', current_user.user_id)
                events = []
            else:
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

            if TELL_USER_ABOUT_ERRORS:
                dispatcher.utter_message(json_message={
                    'text': 'Ouch! Something went wrong 🤖',

                    'parse_mode': 'html',
                    'reply_markup': RESTART_COMMAND_MARKUP,
                })

        else:
            if tracker.get_slot(SWIPER_ERROR_SLOT) is not None:
                events.append(SlotSet(
                    key=SWIPER_ERROR_SLOT,
                    value=None,
                ))
            if tracker.get_slot(SWIPER_ERROR_TRACE_SLOT) is not None:
                events.append(SlotSet(
                    key=SWIPER_ERROR_TRACE_SLOT,
                    value=None,
                ))

        current_user = user_vault.get_user(tracker.sender_id)  # invoke get_user once again (just in case)

        if tracker.get_slot(SWIPER_STATE_SLOT) != current_user.state:
            events.append(SlotSet(
                key=SWIPER_STATE_SLOT,
                value=current_user.state,
            ))
        if tracker.get_slot(rasa_callbacks.PARTNER_ID_SLOT) != current_user.partner_id:
            events.append(SlotSet(
                key=rasa_callbacks.PARTNER_ID_SLOT,
                value=current_user.partner_id,
            ))

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
        return ACTION_SESSION_START_NAME

    def should_update_user_activity_timestamp(self, _tracker: Tracker) -> bool:
        return False

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

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    def offer_chitchat(self, dispatcher: CollectingDispatcher, tracker: Tracker) -> None:
        latest_intent = tracker.get_intent_of_latest_message()

        if latest_intent == 'help':
            dispatcher.utter_message(json_message={  # TODO oleksandr: rewrite this text ?
                'text': 'I can arrange video chitchat with another human for you 🎥 🗣 ☎️\n'
                        '\n'
                        'Here is how it works:\n'
                        '\n'
                        '• I find someone who also wants to chitchat.\n'
                        '• I confirm with you and them that you are both ready.\n'
                        '• I send both of you a video chat link.\n'
                        '\n'
                        '<b>Would you like to give it a try?</b>',

                'parse_mode': 'html',
                'reply_markup': YES_CONNECT_NO_THANKS_MARKUP,
            })

        elif latest_intent == 'out_of_scope':
            self.offer_chitchat_again(dispatcher, "I'm sorry, but I cannot help you with that 🤖")

        else:  # 'greet'
            dispatcher.utter_message(json_message={
                'text': 'Hi, my name is Swipy 🙂\n'
                        '\n'
                        'I randomly connect IT people in one-on-one video calls.\n'
                        '\n'
                        'Here you can:\n'
                        '\n'
                        '• chit-chat 🗣\n'
                        '• expand your network 🕸\n'
                        '• practice spoken English 🇬🇧\n'
                        '\n'
                        '<b>Would you like to have a video call with a random person?</b>',

                'parse_mode': 'html',
                'reply_markup': YES_CONNECT_HOW_DOES_IT_WORK_NO_THANKS_MARKUP,
            })

    # noinspection PyMethodMayBeStatic
    def offer_chitchat_again(self, dispatcher: CollectingDispatcher, intro: Text) -> None:
        dispatcher.utter_message(json_message={
            'text': f"{intro}\n"
                    f"\n"
                    f"<b>Would you like to have a video call with a random person?</b>",

            'parse_mode': 'html',
            'reply_markup': YES_CONNECT_HOW_DOES_IT_WORK_NO_THANKS_MARKUP,
        })

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        if GREETING_MAKES_USER_OK_TO_CHITCHAT:  # TODO oleksandr: is this even useful ? get rid of this completely ?
            if current_user.state in (
                    UserState.NEW,
                    UserState.ASKED_TO_JOIN,
                    UserState.ASKED_TO_CONFIRM,
                    UserState.ROOMED,
                    UserState.REJECTED_JOIN,
                    UserState.REJECTED_CONFIRM,
                    UserState.DO_NOT_DISTURB,
                    UserState.BOT_BLOCKED,
            ):
                # noinspection PyUnresolvedReferences
                current_user.become_ok_to_chitchat()
                current_user.save()

        self.offer_chitchat(dispatcher, tracker)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),

            # TODO oleksandr: why am I even setting these slots here every time ?
            #  set them in BaseSwiperAction and do it only when they change ?
            SlotSet(
                key=DEEPLINK_DATA_SLOT,
                value=current_user.deeplink_data,
            ),
            SlotSet(
                key=TELEGRAM_FROM_SLOT,
                value=current_user.telegram_from,
            ),
        ]


class ActionDefaultFallback(ActionOfferChitchat):
    def name(self) -> Text:
        return ACTION_DEFAULT_FALLBACK_NAME

    def offer_chitchat(self, dispatcher: CollectingDispatcher, tracker: Tracker) -> None:
        self.offer_chitchat_again(dispatcher, "Forgive me, but I've lost track of our conversation 🤖")


class ActionRewind(BaseSwiperAction):  # TODO oleksandr: are you sure it should extend BaseSwiperAction
    def name(self) -> Text:
        return 'action_rewind'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        return [
            UserUtteranceReverted(),
        ]


class ActionStopPartnerSearch(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_stop_partner_search'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        if SEARCH_CANCELLATION_TAKES_A_BREAK:
            # noinspection PyUnresolvedReferences
            current_user.take_a_break()
        else:
            # noinspection PyUnresolvedReferences
            current_user.become_ok_to_chitchat()
        current_user.save()

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionShareContact(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_share_contact'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        username = (current_user.telegram_from or {}).get('username')
        if username:
            if current_user.partner_id:
                partner = user_vault.get_user(current_user.partner_id)
                user_display_name = present_partner_name(current_user.get_first_name(), 'Your last chit-chat partner')

                await rasa_callbacks.share_username(current_user.user_id, partner, user_display_name, username)

                partner_display_name = present_partner_name(partner.get_first_name(), 'your last chit-chat partner')
                dispatcher.utter_message(
                    json_message={
                        'text': f"Your Telegram username has been shared with {partner_display_name}.",

                        'parse_mode': 'html',
                        'reply_markup': CALL_ANOTHER_PERSON_MARKUP,
                    }
                )
            else:
                return [
                    FollowupAction(ACTION_DEFAULT_FALLBACK_NAME),
                ]
        else:
            dispatcher.utter_message(
                json_message={
                    'text': "You don't seem to have a username.\n"
                            "\n"
                            "Please set up a username in your Telegram profile and then try again.",

                    'parse_mode': 'html',
                    'reply_markup': SHARE_MY_CONTACT_CALL_ANOTHER_PERSON_MARKUP,
                }
            )

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionStopTheCall(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_stop_the_call'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        partner = None
        if current_user.latest_room_name:
            await daily_co.delete_room(current_user.latest_room_name)

            if current_user.partner_id:
                partner = user_vault.get_user(current_user.partner_id)

                if partner.is_still_in_the_room(current_user.latest_room_name):
                    await rasa_callbacks.schedule_room_disposal_report(
                        current_user.user_id,
                        partner,
                        current_user.latest_room_name,
                        suppress_callback_errors=True,
                    )

            current_user.latest_room_name = None
            current_user.save()

        if partner:
            dispatcher.utter_message(json_message={
                'text': f"Thank you!\n"
                        f"\n"
                        f"{would_you_like_to_share_contact_with(partner.get_first_name())}",

                'parse_mode': 'html',
                'reply_markup': SHARE_MY_CONTACT_CALL_ANOTHER_PERSON_MARKUP,
            })
        else:
            dispatcher.utter_message(json_message={
                'text': 'Thank you!\n',

                'parse_mode': 'html',
                'reply_markup': CALL_ANOTHER_PERSON_MARKUP,
            })

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionScheduleRoomDisposalReport(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_schedule_room_disposal_report'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return False

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        disposed_room_name = tracker.get_slot(rasa_callbacks.DISPOSED_ROOM_NAME_SLOT)
        if not current_user.is_still_in_the_room(disposed_room_name):
            return [
                UserUtteranceReverted(),
            ]

        return [
            UserUtteranceReverted(),

            reschedule_reminder(
                current_user.user_id,
                EXTERNAL_ROOM_DISPOSAL_REPORT_INTENT,
                ROOM_DISPOSAL_REPORT_DELAY_SEC,
                entities={
                    rasa_callbacks.DISPOSED_ROOM_NAME_SLOT: disposed_room_name,
                },
            ),
        ]


class ActionRoomDisposalReport(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_room_disposal_report'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return False

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        disposed_room_name = tracker.get_slot(rasa_callbacks.DISPOSED_ROOM_NAME_SLOT)
        if not current_user.is_still_in_the_room(disposed_room_name):
            return [
                UserUtteranceReverted(),
            ]

        partner = user_vault.get_user(current_user.partner_id)

        dispatcher.utter_message(json_message={
            'text': f"The call has been stopped.\n"
                    f"\n"
                    f"{would_you_like_to_share_contact_with(partner.get_first_name())}",

            'parse_mode': 'html',
            'reply_markup': SHARE_MY_CONTACT_CALL_ANOTHER_PERSON_MARKUP,
        })

        current_user.latest_room_name = None
        current_user.save()

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionRoomExpirationReport(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_room_expiration_report'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return False

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        disposed_room_name = tracker.get_slot(rasa_callbacks.DISPOSED_ROOM_NAME_SLOT)
        if not current_user.is_still_in_the_room(disposed_room_name):
            return [
                UserUtteranceReverted(),
            ]

        partner = user_vault.get_user(current_user.partner_id)

        dispatcher.utter_message(json_message={
            'text': f"Video call has expired.\n"
                    f"\n"
                    f"{would_you_like_to_share_contact_with(partner.get_first_name())}",

            'parse_mode': 'html',
            'reply_markup': SHARE_MY_CONTACT_CALL_ANOTHER_PERSON_MARKUP,
        })

        current_user.latest_room_name = None
        current_user.save()

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionFindPartner(BaseSwiperAction):
    def name(self) -> Text:
        return ACTION_FIND_PARTNER_NAME

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        if tracker.followup_action == ACTION_FIND_PARTNER_NAME:
            return False
        if self.is_triggered_by_reminder(tracker):
            return False
        return True

    @staticmethod
    def is_triggered_by_reminder(tracker: Tracker) -> bool:
        latest_intent = get_intent_of_latest_message_reliably(tracker)
        return latest_intent == EXTERNAL_FIND_PARTNER_INTENT

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:

        revert_user_utterance = False
        initiate_search = False

        if self.is_triggered_by_reminder(tracker):
            revert_user_utterance = True

            if current_user.state != UserState.WANTS_CHITCHAT:
                # the search was stopped for the user one way or another (user said stop, or was asked to join etc.)
                # => don't do any partner searching and don't schedule another reminder
                return [
                    # get rid of the artificial reminder intent so it doesn't interfere with story predictions
                    UserUtteranceReverted(),
                ]

        else:  # user just requested chitchat
            initiate_search = True

            # noinspection PyUnresolvedReferences
            current_user.request_chitchat()
            if CLEAR_REJECTED_LIST_WHEN_NO_ONE_FOUND:
                previous_action_result = tracker.get_slot(SWIPER_ACTION_RESULT_SLOT)
                if previous_action_result == SwiperActionResult.PARTNER_WAS_NOT_FOUND:
                    current_user.rejected_partner_ids = []
            current_user.save()

        partner = user_vault.get_random_available_partner(current_user)

        if partner:
            user_profile_photo_id = telegram_helpers.get_user_profile_photo_file_id(current_user.user_id)
            user_first_name = current_user.get_first_name()

            await rasa_callbacks.ask_to_join(
                current_user.user_id,
                partner,
                user_profile_photo_id,
                user_first_name,
                suppress_callback_errors=True,
            )

        partner_search_start_ts = get_partner_search_start_ts(tracker)
        if initiate_search or (
                partner_search_start_ts is not None and
                (current_timestamp_int() - partner_search_start_ts) <= PARTNER_SEARCH_TIMEOUT_SEC
        ):
            # we still have time to look for / ask some more people => schedule another reminder
            return [
                # get rid of the artificial reminder intent so it doesn't interfere with story predictions
                UserUtteranceReverted()

                if revert_user_utterance else

                SlotSet(
                    key=SWIPER_ACTION_RESULT_SLOT,
                    value=SwiperActionResult.SUCCESS,
                ),

                *self.schedule_find_partner_reminder(
                    current_user.user_id,
                    initiate=initiate_search,
                ),
            ]

        dispatcher.utter_message(json_message={
            'text': "I've been reaching out to people for two minutes, but no one has responded just yet.\n"
                    "\n"
                    "Which is ok - people rarely respond immediately...\n"
                    "\n"
                    "<b>Would you like me to try some more?</b>",

            'parse_mode': 'html',
            'reply_markup': YES_NO_MARKUP,
        })

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.PARTNER_WAS_NOT_FOUND,
            ),
        ]

    @staticmethod
    def schedule_find_partner_reminder(
            current_user_id: Text,
            delta_sec: float = FIND_PARTNER_FREQUENCY_SEC,
            initiate: bool = False,
    ) -> List[EventType]:
        events = [reschedule_reminder(
            current_user_id,
            EXTERNAL_FIND_PARTNER_INTENT,
            delta_sec,
        )]
        if initiate:
            events.insert(0, SlotSet(
                key=PARTNER_SEARCH_START_TS_SLOT,
                value=str(current_timestamp_int()),
            ))
        return events


class ActionAskToJoin(BaseSwiperAction):
    def name(self) -> Text:
        return ACTION_ASK_TO_JOIN_NAME

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return False

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        partner_id = tracker.get_slot(rasa_callbacks.PARTNER_ID_SLOT)
        partner_photo_file_id = tracker.get_slot(rasa_callbacks.PARTNER_PHOTO_FILE_ID_SLOT)
        partner_first_name = tracker.get_slot(rasa_callbacks.PARTNER_FIRST_NAME_SLOT)

        latest_intent = get_intent_of_latest_message_reliably(tracker)

        presented_partner = present_partner_name(
            partner_first_name,
            'This person' if partner_photo_file_id else 'Someone',
        )

        if latest_intent == EXTERNAL_ASK_TO_JOIN_INTENT:
            # noinspection PyUnresolvedReferences
            current_user.become_asked_to_join(partner_id)
            current_user.save()

            utter_text = (
                f"Hey! {presented_partner} is looking to chitchat 🗣\n"
                f"\n"
                f"<b>Would you like to join a video call?</b> 🎥 ☎️"
            )

        elif latest_intent == EXTERNAL_ASK_TO_CONFIRM_INTENT:
            # noinspection PyUnresolvedReferences
            current_user.become_asked_to_confirm(partner_id)
            current_user.save()

            utter_text = (
                f"Hey! {presented_partner} is willing to chitchat with 👉 you 👈\n"
                f"\n"
                f"<b>Are you ready for a video call?</b> 🎥 ☎️"
            )

        else:
            raise SwiperError(
                f"{repr(self.name())} was triggered by an unexpected intent ({repr(latest_intent)}) - either "
                f"{repr(EXTERNAL_ASK_TO_JOIN_INTENT)} or {repr(EXTERNAL_ASK_TO_CONFIRM_INTENT)} was expected"
            )

        if partner_photo_file_id:
            custom_dict = {
                'photo': partner_photo_file_id,
                'caption': utter_text,
            }
        else:
            custom_dict = {
                'text': utter_text,
            }

        custom_dict['parse_mode'] = 'html'
        custom_dict['reply_markup'] = YES_NO_SOMEONE_ELSE_MARKUP

        dispatcher.utter_message(json_message=custom_dict)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.USER_HAS_BEEN_ASKED,
            ),
        ]


class ActionAcceptInvitation(BaseSwiperAction):
    def name(self) -> Text:
        return ACTION_ACCEPT_INVITATION_NAME

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        if not does_invitation_go_right_before(tracker, current_user):
            latest_intent = tracker.get_intent_of_latest_message()
            if latest_intent == VIDEOCHAT_INTENT:
                # user simply asked for videochat
                dispatcher.utter_message(response=UTTER_OK_LOOKING_FOR_PARTNER_TEMPLATE)

                return [
                    ActionReverted(),
                    FollowupAction(ACTION_FIND_PARTNER_NAME),
                ]
            else:
                # user said yes to something but it wasn't an invitation
                return [
                    ActionReverted(),
                    FollowupAction(ACTION_DEFAULT_FALLBACK_NAME),
                ]

        partner = user_vault.get_user(current_user.partner_id)

        # noinspection PyBroadException
        try:
            if partner.is_waiting_to_be_confirmed_by(current_user.user_id):
                # current user was the one asked to confirm and they just did => create the room
                return await self.create_room(dispatcher, current_user, partner)

            elif partner.chitchat_can_be_offered_by(current_user.user_id):
                # confirm with the partner before creating any rooms
                return await self.confirm_with_partner(dispatcher, current_user, partner)

        except SwiperRasaCallbackError:
            logger.exception('FAILED TO ACCEPT INVITATION')

        return self.partner_gone_start_search(dispatcher, current_user, partner)

    # noinspection PyUnusedLocal
    @staticmethod
    async def create_room(
            dispatcher: CollectingDispatcher,
            current_user: UserStateMachine,
            partner: UserStateMachine,
    ) -> List[Dict[Text, Any]]:
        created_room = await daily_co.create_room(current_user.user_id)
        room_url = created_room['url']
        room_name = created_room['name']

        await rasa_callbacks.join_room(current_user.user_id, partner, room_url, room_name)

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.ROOM_URL_READY,
            ),
            SlotSet(
                key=rasa_callbacks.ROOM_URL_SLOT,
                value=room_url,
            ),
            SlotSet(
                key=rasa_callbacks.ROOM_NAME_SLOT,
                value=room_name,
            ),
            FollowupAction(ACTION_JOIN_ROOM_NAME),
        ]

    @staticmethod
    async def confirm_with_partner(
            dispatcher: CollectingDispatcher,
            current_user: UserStateMachine,
            partner: UserStateMachine,
    ) -> List[Dict[Text, Any]]:
        user_profile_photo_id = telegram_helpers.get_user_profile_photo_file_id(current_user.user_id)
        user_first_name = current_user.get_first_name()

        await rasa_callbacks.ask_to_confirm(
            current_user.user_id,
            partner,
            user_profile_photo_id,
            user_first_name,
        )

        # noinspection PyUnresolvedReferences
        current_user.wait_for_partner_to_confirm(partner.user_id)
        current_user.save()

        dispatcher.utter_message(json_message={
            'text': f"Just a moment, I'm checking if {present_partner_name(partner.get_first_name(), 'that person')} "
                    f"is ready too...\n"
                    f"\n"
                    f"Please don't go anywhere - <b>this will take one minute or less</b> ⏳",

            'parse_mode': 'html',
            'reply_markup': CANCEL_MARKUP,
        })

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.PARTNER_HAS_BEEN_ASKED,
            ),
            reschedule_reminder(
                current_user.user_id,
                EXTERNAL_EXPIRE_PARTNER_CONFIRMATION_INTENT,
                PARTNER_CONFIRMATION_TIMEOUT_SEC,
            ),
        ]

    # noinspection PyUnusedLocal
    @staticmethod
    def partner_gone_start_search(
            dispatcher: CollectingDispatcher,
            current_user: UserStateMachine,
            partner: UserStateMachine,
    ) -> List[Dict[Text, Any]]:
        # noinspection PyUnresolvedReferences
        current_user.become_ok_to_chitchat()
        current_user.save()

        utter_partner_already_gone(dispatcher, partner.get_first_name())

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.PARTNER_NOT_WAITING_ANYMORE,
            ),
        ]


class ActionJoinRoom(BaseSwiperAction):
    def name(self) -> Text:
        return ACTION_JOIN_ROOM_NAME

    @staticmethod
    def is_intent_external(tracker: Tracker):
        latest_intent = get_intent_of_latest_message_reliably(tracker)
        return latest_intent == rasa_callbacks.EXTERNAL_JOIN_ROOM_INTENT

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        if tracker.followup_action == ACTION_JOIN_ROOM_NAME:
            return False
        if self.is_intent_external(tracker):
            return False
        return True
        # it will never return True, though (in current design
        # it is always either a followup or an external intent)

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        partner_id = tracker.get_slot(rasa_callbacks.PARTNER_ID_SLOT)
        room_url = tracker.get_slot(rasa_callbacks.ROOM_URL_SLOT)
        room_name = tracker.get_slot(rasa_callbacks.ROOM_NAME_SLOT)

        if current_user.latest_room_name:
            await daily_co.delete_room(current_user.latest_room_name)

        # noinspection PyUnresolvedReferences
        current_user.join_room(partner_id, room_name)
        current_user.save()

        is_intent_external = self.is_intent_external(tracker)
        utter_room_url(
            dispatcher,
            room_url,
            after_confirming_with_partner=is_intent_external,
        )

        expiration_reminder_delay_sec = daily_co.DAILY_CO_MEETING_DURATION_SEC
        if is_intent_external:
            # make sure room expiration reports arrive to partners at slightly different time (otherwise we seem to be
            # hitting telegram limits sometimes - one of the partners doesn't always receive this report)
            expiration_reminder_delay_sec += 1

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
            reschedule_reminder(
                current_user.user_id,
                EXTERNAL_ROOM_EXPIRATION_REPORT_INTENT,
                expiration_reminder_delay_sec,
                entities={
                    rasa_callbacks.DISPOSED_ROOM_NAME_SLOT: room_name,
                },
            ),
        ]


def would_you_like_to_share_contact_with(partner_first_name: Text) -> Text:
    partner_display_name = present_partner_name(
        partner_first_name,
        'your last chit-chat partner',
    )
    return f"Would you like to share your Telegram contact info with {partner_display_name} to stay in touch?"


def utter_room_url(dispatcher: CollectingDispatcher, room_url: Text, after_confirming_with_partner: bool):
    shout = 'Done!' if after_confirming_with_partner else 'Awesome!'
    dispatcher.utter_message(json_message={
        'text': f"{shout} ✅ 🎉\n"
                f"\n"
                f"<b>Please follow this link to join the video call:</b>\n"
                f"\n"
                f"{room_url}",

        'parse_mode': 'html',
        'reply_markup': STOP_THE_CALL_MARKUP,
    })


class ActionDoNotDisturb(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_do_not_disturb'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        # noinspection PyUnresolvedReferences
        current_user.become_do_not_disturb()
        current_user.save()

        dispatcher.utter_message(json_message={
            'text': 'Ok, I will not be sending invitations anymore 🛑',

            'parse_mode': 'html',
            'reply_markup': RESTART_COMMAND_MARKUP,
        })

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionRejectInvitation(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_reject_invitation'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        latest_intent = tracker.get_intent_of_latest_message()
        user_wants_a_different_partner = latest_intent == SOMEONE_ELSE_INTENT

        if not does_invitation_go_right_before(tracker, current_user):
            if user_wants_a_different_partner:
                # it's not a rejection at all - user simply asked for videochat
                dispatcher.utter_message(response=UTTER_OK_LOOKING_FOR_PARTNER_TEMPLATE)

                return [
                    ActionReverted(),
                    FollowupAction(ACTION_FIND_PARTNER_NAME),
                ]
            else:
                # user rejected something but it wasn't an invitation
                return [
                    ActionReverted(),
                    FollowupAction(ACTION_DEFAULT_FALLBACK_NAME),
                ]

        is_asked_to_confirm = current_user.state == UserState.ASKED_TO_CONFIRM
        partner_id = current_user.partner_id

        if user_wants_a_different_partner:
            # noinspection PyUnresolvedReferences
            current_user.reject_partner()

            dispatcher.utter_message(response=UTTER_OK_LOOKING_FOR_PARTNER_TEMPLATE)
        else:
            # noinspection PyUnresolvedReferences
            current_user.reject_invitation()

            dispatcher.utter_message(json_message={
                'text': UTTER_INVITATION_DECLINED,
                'parse_mode': 'html',
                'reply_markup': RESTART_COMMAND_MARKUP,
            })

        current_user.save()

        if is_asked_to_confirm:  # as opposed to asked_to_join
            partner = user_vault.get_user(partner_id)

            if partner.is_waiting_to_be_confirmed_by(current_user.user_id):
                # don't leave the rejected partner waiting for nothing
                await rasa_callbacks.reject_confirmation(
                    current_user.user_id,
                    partner,
                    suppress_callback_errors=True,
                )

        events = [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]
        if user_wants_a_different_partner:
            events.append(FollowupAction(ACTION_FIND_PARTNER_NAME))
        return events


class ActionCancelAcceptedInvitation(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_cancel_accepted_invitation'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        if WAITING_CANCELLATION_REJECTS_INVITATION:
            # noinspection PyUnresolvedReferences
            current_user.reject_invitation()
        else:
            # noinspection PyUnresolvedReferences
            current_user.become_ok_to_chitchat()
        current_user.save()

        dispatcher.utter_message(json_message={
            'text': UTTER_INVITATION_DECLINED,
            'parse_mode': 'html',
            'reply_markup': RESTART_COMMAND_MARKUP,
        })

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionExpirePartnerConfirmation(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_expire_partner_confirmation'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return False

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        if current_user.state != UserState.WAITING_PARTNER_CONFIRM:
            # user was not waiting for anybody's confirmation anymore anyway => do nothing and cover your tracks
            return [
                UserUtteranceReverted(),
            ]

        latest_intent = get_intent_of_latest_message_reliably(tracker)
        if latest_intent == rasa_callbacks.EXTERNAL_PARTNER_DID_NOT_CONFIRM_INTENT:
            # this is not a reminder (partner rejected confirmation explicitly)
            partner_id_that_rejected = tracker.get_slot(rasa_callbacks.PARTNER_ID_THAT_REJECTED_SLOT)

            if not current_user.is_waiting_to_be_confirmed_by(partner_id_that_rejected):
                # user is not waiting for this particular partner anymore anyway => ignore
                return [
                    UserUtteranceReverted(),
                ]

        partner_id = current_user.partner_id

        # noinspection PyUnresolvedReferences
        current_user.become_ok_to_chitchat()
        current_user.save()

        partner = user_vault.get_user(partner_id)
        utter_partner_already_gone(dispatcher, partner.get_first_name())

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionClearFeedbackSlot(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_clear_feedback_slot'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        return [
            SlotSet(
                key=FEEDBACK_TEXT_SLOT,
                value=None,
            ),
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionTakeAShortBreak(BaseSwiperAction):
    def name(self) -> Text:
        return 'action_take_a_short_break'

    def should_update_user_activity_timestamp(self, tracker: Tracker) -> bool:
        return True

    async def swipy_run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
            current_user: UserStateMachine,
            user_vault: IUserVault,
    ) -> List[Dict[Text, Any]]:
        if current_user.chitchat_can_be_offered(seconds_later=SHORT_BREAK_TIMEOUT_SEC):
            # noinspection PyUnresolvedReferences
            current_user.take_a_short_break()
            current_user.save()

        return [
            SlotSet(
                key=SWIPER_ACTION_RESULT_SLOT,
                value=SwiperActionResult.SUCCESS,
            ),
        ]


class ActionMakeEveryoneAvailable(Action):  # TODO oleksandr: DO NOT SHIP IT TO PROD !!!!!!!!!!!!!!!!!!!!!!!!!
    def name(self) -> Text:
        return 'action_make_everyone_available'

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        from actions.aws_resources import user_state_machine_table

        counter = 0
        for item in user_state_machine_table.scan()['Items']:
            user_state_machine_table.update_item(
                Key={'user_id': item['user_id']},
                UpdateExpression='SET #state=:state REMOVE #roomed, #rejected, #seen',  # , #room_name',
                ExpressionAttributeNames={
                    # '#room_name': 'latest_room_name',
                    '#roomed': 'roomed_partner_ids',
                    '#rejected': 'rejected_partner_ids',
                    '#seen': 'seen_partner_ids',
                    '#state': 'state',
                },
                ExpressionAttributeValues={':state': UserState.OK_TO_CHITCHAT},
            )
            counter += 1

        dispatcher.utter_message(text=f"DONE FOR {counter} ITEMS")
        return []


def does_invitation_go_right_before(tracker: Tracker, current_user: UserStateMachine):
    filtered_reversed_applied_events = filter(
        lambda e: e.get('event') == 'action' and e.get('name') not in [ACTION_LISTEN_NAME, ACTION_SESSION_START_NAME],
        reversed(tracker.applied_events()),
    )
    try:
        previous_action = next(filtered_reversed_applied_events)
        return previous_action.get('name') == ACTION_ASK_TO_JOIN_NAME
    except StopIteration:
        # event history is lost (probably due to redeploy) => let's resort to a less precise way of checking
        return current_user.state in [
            UserState.ASKED_TO_JOIN,
            UserState.ASKED_TO_CONFIRM,
        ]


def utter_partner_already_gone(dispatcher: CollectingDispatcher, partner_first_name: Text):
    dispatcher.utter_message(json_message={
        'text': f"Unfortunately, {present_partner_name(partner_first_name, 'that person')} has become unavailable 😵\n"
                f"\n"
                f"<b>Would you like to connect with someone else?</b>",

        'parse_mode': 'html',
        'reply_markup': SOMEONE_ELSE_NO_MARKUP,
    })


def get_partner_search_start_ts(tracker: Tracker) -> int:
    ts_str = tracker.get_slot(PARTNER_SEARCH_START_TS_SLOT)
    return int(ts_str) if ts_str else None


def reschedule_reminder(
        current_user_id: Text,
        intent_name: Text,
        delta_sec: float,
        entities: Optional[Union[List[Dict[Text, Any]], Dict[Text, Text]]] = None,
        kill_on_user_message: bool = False,
) -> EventType:
    date = datetime_now() + datetime.timedelta(seconds=delta_sec)

    reminder = ReminderScheduled(
        intent_name,
        trigger_date_time=date,
        entities=entities,
        name=current_user_id + intent_name,  # unique per user and can be rescheduled for the user
        kill_on_user_message=kill_on_user_message,
    )
    return reminder
