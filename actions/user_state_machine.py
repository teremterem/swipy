from dataclasses import dataclass
from datetime import datetime
from typing import Text, Optional

from transitions import Machine

from actions.utils import current_timestamp_int


class UserState:
    NEW = 'new'
    WANTS_CHITCHAT = 'wants_chitchat'
    OK_TO_CHITCHAT = 'ok_to_chitchat'
    WAITING_PARTNER_JOIN = 'waiting_partner_join'
    WAITING_PARTNER_CONFIRM = 'waiting_partner_confirm'
    ASKED_TO_JOIN = 'asked_to_join'
    ASKED_TO_CONFIRM = 'asked_to_confirm'
    ROOMED = 'roomed'
    REJECTED_JOIN = 'rejected_join'
    REJECTED_CONFIRM = 'rejected_confirm'
    JOIN_TIMED_OUT = 'join_timed_out'
    CONFIRM_TIMED_OUT = 'confirm_timed_out'
    DO_NOT_DISTURB = 'do_not_disturb'

    all = [
        NEW,
        WANTS_CHITCHAT,
        OK_TO_CHITCHAT,
        WAITING_PARTNER_JOIN,
        WAITING_PARTNER_CONFIRM,
        ASKED_TO_JOIN,
        ASKED_TO_CONFIRM,
        ROOMED,
        REJECTED_JOIN,
        REJECTED_CONFIRM,
        JOIN_TIMED_OUT,
        CONFIRM_TIMED_OUT,
        DO_NOT_DISTURB,
    ]


@dataclass
class UserModel:
    user_id: Text
    state: Text = None  # the state machine will set it to UserState.NEW if not provided explicitly
    partner_id: Optional[Text] = None
    newbie: bool = True
    state_timestamp: Optional[int] = None
    state_timestamp_str: Optional[Text] = None
    notes: Text = ''


class UserStateMachine(UserModel):
    def __init__(self, *args, state: Text = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.machine = Machine(
            model=self,
            states=UserState.all,
            initial=UserState.NEW,
            auto_transitions=False,
            send_event=True,
            after_state_change=[
                self._update_state_timestamp,
            ],
        )
        if state is not None:
            self.machine.set_state(state)

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='request_chitchat',
            source='*',
            dest=UserState.WANTS_CHITCHAT,
            after=[
                self._drop_partner_id,
            ],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_ok_to_chitchat',
            source='*',
            dest=UserState.OK_TO_CHITCHAT,
            after=[
                self._drop_partner_id,
            ],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='wait_partner_join',
            source=UserState.WANTS_CHITCHAT,
            dest=UserState.WAITING_PARTNER_JOIN,
            after=[
                self._set_partner_id,
            ],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_asked_to_confirm',
            source=UserState.WAITING_PARTNER_JOIN,
            dest=UserState.ASKED_TO_CONFIRM,
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_asked_to_join',
            source=[
                UserState.WANTS_CHITCHAT,
                UserState.OK_TO_CHITCHAT,
                UserState.ROOMED,
                UserState.REJECTED_JOIN,
                UserState.REJECTED_CONFIRM,
                UserState.JOIN_TIMED_OUT,
                UserState.CONFIRM_TIMED_OUT,
            ],
            dest=UserState.ASKED_TO_JOIN,
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
            after=[
                self._graduate_from_newbie,
                self._drop_partner_id,
            ],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_do_not_disturb',
            source='*',
            dest=UserState.DO_NOT_DISTURB,
            after=[
                self._drop_partner_id,
            ],
        )
        # TODO reject_join
        # TODO reject_confirm
        # TODO time_join_out
        # TODO time_confirm_out

    def is_waiting_for(self, partner_id):
        if not partner_id:
            return False

        return self.partner_id == partner_id and self.state in (
            UserState.WAITING_PARTNER_JOIN,
            UserState.WAITING_PARTNER_CONFIRM,
        )

    def _set_partner_id(self, event) -> None:
        self.partner_id = event.args[0]

    # noinspection PyUnusedLocal
    def _drop_partner_id(self, event) -> None:
        self.partner_id = None

    # noinspection PyUnusedLocal
    def _graduate_from_newbie(self, event) -> None:
        self.newbie = False

    # noinspection PyUnusedLocal
    def _update_state_timestamp(self, event) -> None:
        if event.transition.source == event.transition.dest:
            # state hasn't changed => no need to update timestamp
            return

        self.state_timestamp = current_timestamp_int()
        self.state_timestamp_str = datetime.utcfromtimestamp(self.state_timestamp).strftime('%Y-%m-%d %H:%M:%S Z')
