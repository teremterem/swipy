import os
import random
from dataclasses import dataclass, field
from typing import Text, Optional, Dict, Any, TYPE_CHECKING, List

from transitions import Machine, EventData

from actions.utils import current_timestamp_int, SwiperStateMachineError, format_swipy_timestamp, SwiperError

if TYPE_CHECKING:
    from actions.user_vault import IUserVault

SWIPER_STATE_MIN_TIMEOUT_SEC = int(os.getenv('SWIPER_STATE_MIN_TIMEOUT_SEC', '14400'))  # 4 hours (4*60*60 seconds)
SWIPER_STATE_MAX_TIMEOUT_SEC = int(os.getenv('SWIPER_STATE_MAX_TIMEOUT_SEC', '241200'))  # 67 hours (67*60*60 seconds)
ROOMED_STATE_TIMEOUT_SEC = int(os.getenv('ROOMED_STATE_TIMEOUT_SEC', '900'))  # 15 minutes (15*60 seconds)
PARTNER_CONFIRMATION_TIMEOUT_SEC = int(os.getenv('PARTNER_CONFIRMATION_TIMEOUT_SEC', '60'))  # 1 minute
NUM_OF_ROOMED_PARTNERS_TO_REMEMBER = int(os.getenv('NUM_OF_ROOMED_PARTNERS_TO_REMEMBER', '5'))

NATIVE_UNKNOWN = 'unknown'


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
    roomed_partner_ids: List[Text] = field(default_factory=list)
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
            ],
            after=[
                self._exclude_current_partner_id,
                self._graduate_from_newbie,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='reject',
            source=[
                UserState.ASKED_TO_JOIN,
            ],
            dest=UserState.REJECTED_JOIN,
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='reject',
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

    def has_become_discoverable(self):
        if not self.state_timeout_ts:  # 0 and None are treated equally
            return True  # users in states that don't support timeouts are immediately discoverable

        return self.state_timeout_ts < current_timestamp_int()

    def chitchat_can_be_offered(self):
        return self.state in UserState.offerable_states and self.has_become_discoverable()

    @staticmethod
    def _assert_partner_id_arg_not_empty(event: EventData) -> None:
        if not event.args or not event.args[0]:
            raise SwiperStateMachineError('no or empty partner_id was passed')

    def _assert_partner_id_arg_same(self, event: EventData) -> None:
        partner_id = event.args[0]
        if self.partner_id != partner_id:
            raise SwiperStateMachineError(
                f"partner_id that was passed ({repr(partner_id)}) "
                f"differs from partner_id that was set before ({repr(self.partner_id)})"
            )

    def _set_partner_id(self, event: EventData) -> None:
        self.partner_id = event.args[0]

    # noinspection PyUnusedLocal
    def _drop_partner_id(self, event: EventData) -> None:
        self.partner_id = None

    # noinspection PyUnusedLocal
    def _exclude_current_partner_id(self, event: EventData) -> None:
        if NUM_OF_ROOMED_PARTNERS_TO_REMEMBER > 1:
            self.roomed_partner_ids = self.roomed_partner_ids[-NUM_OF_ROOMED_PARTNERS_TO_REMEMBER + 1:]
            self.roomed_partner_ids.append(self.partner_id)

        elif NUM_OF_ROOMED_PARTNERS_TO_REMEMBER == 1:
            self.roomed_partner_ids = [self.partner_id]
        else:
            self.roomed_partner_ids = []

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

            if event.transition.dest == UserState.WAITING_PARTNER_CONFIRM:
                timeout = PARTNER_CONFIRMATION_TIMEOUT_SEC
            elif event.transition.dest == UserState.ROOMED:
                timeout = ROOMED_STATE_TIMEOUT_SEC
            else:
                # TODO oleksandr: care to switch to secrets ?
                timeout = random.randint(SWIPER_STATE_MIN_TIMEOUT_SEC, SWIPER_STATE_MAX_TIMEOUT_SEC)

            self.state_timeout_ts = self.state_timestamp + timeout
            self.state_timeout_ts_str = format_swipy_timestamp(self.state_timeout_ts)

        else:
            self.state_timeout_ts = 0  # DDB GSI does not allow None
            self.state_timeout_ts_str = None
