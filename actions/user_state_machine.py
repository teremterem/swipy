import os
from dataclasses import dataclass
from datetime import datetime
from distutils.util import strtobool
from typing import Text, Optional

from transitions import Machine, EventData

from actions.utils import current_timestamp_int

TIMED_OUT_ARE_OK_TO_CHITCHAT = strtobool(os.getenv('TIMED_OUT_ARE_OK_TO_CHITCHAT', 'no'))


class UserState:
    NEW = 'new'
    WANTS_CHITCHAT = 'wants_chitchat'
    OK_TO_CHITCHAT = 'ok_to_chitchat'
    WAITING_PARTNER_JOIN = 'waiting_partner_join'
    WAITING_PARTNER_CONFIRM = 'waiting_partner_confirm'
    ASKED_TO_JOIN = 'asked_to_join'
    ASKED_TO_CONFIRM = 'asked_to_confirm'
    ROOMED = 'roomed'  # logically equivalent to 'ok_to_chitchat' (except they may still be on a call)
    REJECTED_JOIN = 'rejected_join'
    REJECTED_CONFIRM = 'rejected_confirm'
    JOIN_TIMED_OUT = 'join_timed_out'
    CONFIRM_TIMED_OUT = 'confirm_timed_out'
    DO_NOT_DISTURB = 'do_not_disturb'

    all_states = [
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

    can_be_offered_chitchat_states = [
        WANTS_CHITCHAT,
        OK_TO_CHITCHAT,
        ROOMED,
        REJECTED_JOIN,
        REJECTED_CONFIRM,
    ]
    if TIMED_OUT_ARE_OK_TO_CHITCHAT:
        can_be_offered_chitchat_states.extend([
            JOIN_TIMED_OUT,
            CONFIRM_TIMED_OUT,
        ])


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
            states=UserState.all_states,
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
            trigger='become_do_not_disturb',
            source='*',
            dest=UserState.DO_NOT_DISTURB,
            after=[
                self._drop_partner_id,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='wait_for_partner',
            source=[
                UserState.WANTS_CHITCHAT,
            ],
            dest=UserState.WAITING_PARTNER_JOIN,
            before=[
                self._assert_partner_id_arg_not_empty,
            ],
            after=[
                self._set_partner_id,
            ],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='wait_for_partner',
            source=[
                UserState.ASKED_TO_JOIN,
            ],
            dest=UserState.WAITING_PARTNER_CONFIRM,
            before=[
                self._assert_partner_id_arg_not_empty,
                self._assert_partner_id_arg_same,
            ],
        )

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_asked',
            source=[
                UserState.WAITING_PARTNER_JOIN,
            ],
            dest=UserState.ASKED_TO_CONFIRM,
            before=[
                self._assert_partner_id_arg_not_empty,
                self._assert_partner_id_arg_same,
            ],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_asked',
            source=UserState.can_be_offered_chitchat_states,
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
            trigger='time_out',
            source=[
                UserState.ASKED_TO_JOIN,
            ],
            dest=UserState.JOIN_TIMED_OUT,
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='time_out',
            source=[
                UserState.ASKED_TO_CONFIRM,
            ],
            dest=UserState.CONFIRM_TIMED_OUT,
        )

    def is_waiting_for(self, partner_id: Optional[Text]):
        if not partner_id:
            return False

        return self.partner_id == partner_id and self.state in (
            UserState.WAITING_PARTNER_JOIN,
            UserState.WAITING_PARTNER_CONFIRM,
        )

    def can_be_offered_chitchat(self):
        return self.state in UserState.can_be_offered_chitchat_states

    @staticmethod
    def _assert_partner_id_arg_not_empty(event: EventData) -> None:
        if not event.args or not event.args[0]:
            raise ValueError('no or empty partner_id was passed')

    def _assert_partner_id_arg_same(self, event: EventData) -> None:
        partner_id = event.args[0]
        if self.partner_id != partner_id:
            raise ValueError(
                f"partner_id that was passed ({repr(partner_id)}) "
                f"differs from partner_id that was set before ({repr(self.partner_id)})"
            )

    def _set_partner_id(self, event: EventData) -> None:
        self.partner_id = event.args[0]

    # noinspection PyUnusedLocal
    def _drop_partner_id(self, event: EventData) -> None:
        self.partner_id = None

    # noinspection PyUnusedLocal
    def _graduate_from_newbie(self, event: EventData) -> None:
        self.newbie = False

    # noinspection PyUnusedLocal
    def _update_state_timestamp(self, event: EventData) -> None:
        if event.transition.source == event.transition.dest:
            # state hasn't changed => no need to update timestamp
            return

        self.state_timestamp = current_timestamp_int()
        self.state_timestamp_str = datetime.utcfromtimestamp(self.state_timestamp).strftime('%Y-%m-%d %H:%M:%S Z')
