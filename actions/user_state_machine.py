import os
import random
from dataclasses import dataclass, field
from typing import Text, Optional, Dict, Any, TYPE_CHECKING, List

from transitions import Machine, EventData

from actions.daily_co import DAILY_CO_MEETING_DURATION_SEC
from actions.utils import current_timestamp_int, SwiperStateMachineError, format_swipy_timestamp, SwiperError, \
    roll_the_list

if TYPE_CHECKING:
    from actions.user_vault import IUserVault

SWIPER_STATE_MIN_TIMEOUT_SEC = int(os.getenv('SWIPER_STATE_MIN_TIMEOUT_SEC', '14400'))  # 4 hours (4*60*60 seconds)
SWIPER_STATE_MAX_TIMEOUT_SEC = int(os.getenv('SWIPER_STATE_MAX_TIMEOUT_SEC', '241200'))  # 67 hours (67*60*60 seconds)
PARTNER_CONFIRMATION_TIMEOUT_SEC = int(os.getenv('PARTNER_CONFIRMATION_TIMEOUT_SEC', '60'))  # 1 minute
SHORT_BREAK_TIMEOUT_SEC = int(os.getenv('SHORT_BREAK_TIMEOUT_SEC', '900'))  # 15 minutes
NUM_OF_ROOMED_PARTNERS_TO_REMEMBER = int(os.getenv('NUM_OF_ROOMED_PARTNERS_TO_REMEMBER', '3'))
NUM_OF_REJECTED_PARTNERS_TO_REMEMBER = int(os.getenv('NUM_OF_REJECTED_PARTNERS_TO_REMEMBER', '21'))
NUM_OF_SEEN_PARTNERS_TO_REMEMBER = int(os.getenv('NUM_OF_SEEN_PARTNERS_TO_REMEMBER', '1'))

NATIVE_UNKNOWN = 'unknown'

TAKE_A_SHORT_BREAK_TRIGGER = 'take_a_short_break'


class UserState:
    NEW = 'new'
    WANTS_CHITCHAT = 'wants_chitchat'
    OK_TO_CHITCHAT = 'ok_to_chitchat'
    WAITING_PARTNER_CONFIRM = 'waiting_partner_confirm'
    ASKED_TO_JOIN = 'asked_to_join'
    ASKED_TO_CONFIRM = 'asked_to_confirm'
    ROOMED = 'roomed'
    REJECTED_JOIN = 'rejected_join'
    REJECTED_CONFIRM = 'rejected_confirm'
    TAKE_A_BREAK = 'take_a_break'
    DO_NOT_DISTURB = 'do_not_disturb'
    BOT_BLOCKED = 'bot_blocked'
    USER_BANNED = 'user_banned'

    all_states_except_user_banned = [
        NEW,
        WANTS_CHITCHAT,
        OK_TO_CHITCHAT,
        WAITING_PARTNER_CONFIRM,
        ASKED_TO_JOIN,
        ASKED_TO_CONFIRM,
        ROOMED,
        REJECTED_JOIN,
        REJECTED_CONFIRM,
        TAKE_A_BREAK,
        DO_NOT_DISTURB,
        BOT_BLOCKED,
    ]
    all_states = all_states_except_user_banned + [
        USER_BANNED,
    ]

    states_with_timeouts = [
        WAITING_PARTNER_CONFIRM,
        ASKED_TO_JOIN,
        ASKED_TO_CONFIRM,
        ROOMED,
        REJECTED_JOIN,
        REJECTED_CONFIRM,
        TAKE_A_BREAK,
    ]
    offerable_states = [
                           WANTS_CHITCHAT,
                           OK_TO_CHITCHAT,
                       ] + states_with_timeouts

    offerable_tiers = [  # TODO oleksandr: do we really need the concept of tiers ?
        offerable_states,  # everything is in one tier for now - we are differentiating only by recency of activity
    ]


@dataclass
class UserModel:
    user_id: Text
    state: Text = None  # the state machine will set it to UserState.NEW if not provided explicitly
    partner_id: Optional[Text] = None
    latest_room_name: Optional[Text] = None
    roomed_partner_ids: List[Text] = field(default_factory=list)
    rejected_partner_ids: List[Text] = field(default_factory=list)
    seen_partner_ids: List[Text] = field(default_factory=list)
    newbie: bool = True
    state_timestamp: int = 0  # DDB GSI does not allow None
    state_timestamp_str: Optional[Text] = None
    state_timeout_ts: int = 0  # DDB GSI does not allow None
    state_timeout_ts_str: Optional[Text] = None
    activity_timestamp: int = 0  # DDB GSI does not allow None
    activity_timestamp_str: Optional[Text] = None
    notes: Text = ''
    deeplink_data: Text = ''
    native: Text = NATIVE_UNKNOWN
    teleg_lang_code: Optional[Text] = None
    telegram_from: Optional[Dict[Text, Any]] = None


class UserStateMachine(UserModel):
    def __init__(self, *args, state: Text = None, user_vault: Optional['IUserVault'] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.machine = Machine(
            model=self,
            states=UserState.all_states,
            initial=UserState.NEW,
            auto_transitions=False,
            send_event=True,
            after_state_change=[
                self._update_state_timestamp,
                self._update_state_timeout_ts,
            ],
        )
        if state is not None:
            self.machine.set_state(state)

        self._user_vault = user_vault

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='request_chitchat',
            source=UserState.all_states_except_user_banned,
            dest=UserState.WANTS_CHITCHAT,
            after=[
                self._clear_seen_partner_id_list,  # increase chances to be found
                self._drop_partner_id,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_ok_to_chitchat',
            source=UserState.all_states_except_user_banned,
            dest=UserState.OK_TO_CHITCHAT,
            after=[
                self._drop_partner_id,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='take_a_break',
            source=UserState.all_states_except_user_banned,
            dest=UserState.TAKE_A_BREAK,
            after=[
                self._drop_partner_id,
            ],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger=TAKE_A_SHORT_BREAK_TRIGGER,
            source=UserState.all_states_except_user_banned,
            dest=UserState.TAKE_A_BREAK,
            after=[
                self._drop_partner_id,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='wait_for_partner_to_confirm',
            source=UserState.all_states_except_user_banned,
            dest=UserState.WAITING_PARTNER_CONFIRM,
            before=[
                self._assert_partner_id_arg_not_empty,
            ],
            after=[
                self._set_partner_id,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_asked_to_join',
            source=UserState.all_states_except_user_banned,
            dest=UserState.ASKED_TO_JOIN,
            before=[
                self._assert_partner_id_arg_not_empty,
            ],
            after=[
                self._set_partner_id,
                self._mark_current_partner_id_as_seen,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_asked_to_confirm',
            source=UserState.all_states_except_user_banned,
            dest=UserState.ASKED_TO_CONFIRM,
            before=[
                self._assert_partner_id_arg_not_empty,
            ],
            after=[
                self._set_partner_id,
                self._mark_current_partner_id_as_seen,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='join_room',
            source=[
                UserState.ASKED_TO_CONFIRM,
                UserState.WAITING_PARTNER_CONFIRM,
            ],
            dest=UserState.ROOMED,
            before=[
                self._assert_partner_id_arg_not_empty,
                self._assert_partner_id_arg_same,
                self._assert_room_name_arg_not_empty,
            ],
            after=[
                self._set_latest_room_name,
                self._mark_current_partner_id_as_roomed,
                self._graduate_from_newbie,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='reject_partner',
            source=[
                UserState.ASKED_TO_JOIN,
                UserState.WAITING_PARTNER_CONFIRM,
            ],
            dest=UserState.REJECTED_JOIN,
            after=[
                self._mark_current_partner_id_as_rejected,
            ],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='reject_partner',
            source=[
                UserState.ASKED_TO_CONFIRM,
            ],
            dest=UserState.REJECTED_CONFIRM,
            after=[
                self._mark_current_partner_id_as_rejected,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='reject_invitation',
            source=[
                UserState.ASKED_TO_JOIN,
                UserState.WAITING_PARTNER_CONFIRM,
            ],
            dest=UserState.REJECTED_JOIN,
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='reject_invitation',
            source=[
                UserState.ASKED_TO_CONFIRM,
            ],
            dest=UserState.REJECTED_CONFIRM,
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_do_not_disturb',
            source=UserState.all_states_except_user_banned,
            dest=UserState.DO_NOT_DISTURB,
            after=[
                self._drop_partner_id,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='mark_as_bot_blocked',
            source=UserState.all_states_except_user_banned,
            dest=UserState.BOT_BLOCKED,
        )

    def get_first_name(self):
        first_name = (self.telegram_from or {}).get('first_name') or None
        return first_name

    def save(self):
        if not self._user_vault:
            raise SwiperError('an attempt to save UserStateMachine that is not associated with any IUserVault instance')
        self._user_vault.save(self)

    def is_waiting_to_be_confirmed_by(self, partner_id: Text):
        if not partner_id:
            return False

        return self.is_waiting_to_be_confirmed() and self.partner_id == partner_id

    def is_waiting_to_be_confirmed(self):
        return self.state == UserState.WAITING_PARTNER_CONFIRM and \
               not self.has_become_discoverable()  # the state hasn't timed out yet

    def has_become_discoverable(self, seconds_later: int = 0):
        if not self.state_timeout_ts:  # 0 and None are treated equally
            return True  # users in states that don't support timeouts are immediately discoverable

        return self.state_timeout_ts < current_timestamp_int() + seconds_later

    def chitchat_can_be_offered_by(self, partner_id: Text, seconds_later: int = 0):
        if not partner_id:
            return False

        return self.chitchat_can_be_offered(seconds_later=seconds_later) and not (
                partner_id in (self.roomed_partner_ids or []) or
                partner_id in (self.rejected_partner_ids or [])
        )

    def chitchat_can_be_offered(self, seconds_later: int = 0):
        return self.state in UserState.offerable_states and self.has_become_discoverable(seconds_later=seconds_later)

    def is_still_in_the_room(self, room_name: Text):
        return room_name and self.state == UserState.ROOMED and self.latest_room_name == room_name

    @staticmethod
    def _assert_partner_id_arg_not_empty(event: EventData) -> None:
        if not event.args or not event.args[0]:
            raise SwiperStateMachineError('no or empty partner_id was passed')

    @staticmethod
    def _assert_room_name_arg_not_empty(event: EventData) -> None:
        if not event.args or len(event.args) < 2 or not event.args[1]:
            raise SwiperStateMachineError('no or empty room_name was passed')

    def _assert_partner_id_arg_same(self, event: EventData) -> None:
        partner_id = event.args[0]
        if self.partner_id != partner_id:
            raise SwiperStateMachineError(
                f"partner_id that was passed ({repr(partner_id)}) "
                f"differs from partner_id that was set before ({repr(self.partner_id)})"
            )

    def _set_partner_id(self, event: EventData) -> None:
        self.partner_id = event.args[0]

    def _set_latest_room_name(self, event: EventData) -> None:
        self.latest_room_name = event.args[1]

    # noinspection PyUnusedLocal
    def _drop_partner_id(self, event: EventData) -> None:
        self.partner_id = None

    # noinspection PyUnusedLocal
    def _mark_current_partner_id_as_roomed(self, event: EventData) -> None:
        self.roomed_partner_ids = roll_the_list(
            self.roomed_partner_ids,
            self.partner_id,
            NUM_OF_ROOMED_PARTNERS_TO_REMEMBER,
        )

    # noinspection PyUnusedLocal
    def _mark_current_partner_id_as_rejected(self, event: EventData) -> None:
        self.rejected_partner_ids = roll_the_list(
            self.rejected_partner_ids,
            self.partner_id,
            NUM_OF_REJECTED_PARTNERS_TO_REMEMBER,
        )

    # noinspection PyUnusedLocal
    def _mark_current_partner_id_as_seen(self, event: EventData) -> None:
        self.seen_partner_ids = roll_the_list(
            self.seen_partner_ids,
            self.partner_id,
            NUM_OF_SEEN_PARTNERS_TO_REMEMBER,
        )

    # noinspection PyUnusedLocal
    def _clear_seen_partner_id_list(self, event: EventData) -> None:
        self.seen_partner_ids = []

    # noinspection PyUnusedLocal
    def _graduate_from_newbie(self, event: EventData) -> None:
        self.newbie = False

    def update_activity_timestamp(self) -> None:
        self.activity_timestamp = current_timestamp_int()
        self.activity_timestamp_str = format_swipy_timestamp(self.activity_timestamp)

    # noinspection PyUnusedLocal
    def _update_state_timestamp(self, event: EventData) -> None:
        self.state_timestamp = current_timestamp_int()
        self.state_timestamp_str = format_swipy_timestamp(self.state_timestamp)

    # noinspection PyUnusedLocal
    def _update_state_timeout_ts(self, event: EventData) -> None:
        if event.transition.dest in UserState.states_with_timeouts:

            if event.event.name == TAKE_A_SHORT_BREAK_TRIGGER:
                timeout = SHORT_BREAK_TIMEOUT_SEC

            elif event.transition.dest == UserState.WAITING_PARTNER_CONFIRM:
                timeout = PARTNER_CONFIRMATION_TIMEOUT_SEC
            else:
                timeout = random.randint(SWIPER_STATE_MIN_TIMEOUT_SEC, SWIPER_STATE_MAX_TIMEOUT_SEC)

            self.state_timeout_ts = self.state_timestamp + timeout
            self.state_timeout_ts_str = format_swipy_timestamp(self.state_timeout_ts)

        else:
            self.state_timeout_ts = 0  # DDB GSI does not allow None
            self.state_timeout_ts_str = None
