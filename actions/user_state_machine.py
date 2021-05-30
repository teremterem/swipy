from dataclasses import dataclass
from datetime import datetime
from typing import Text, Optional

from transitions import Machine

from actions.utils import current_timestamp_int


class UserState:
    NEW = 'new'
    WAITING_PARTNER_ANSWER = 'waiting_partner_answer'
    OK_TO_CHITCHAT = 'ok_to_chitchat'
    ASKED_TO_JOIN = 'asked_to_join'
    DO_NOT_DISTURB = 'do_not_disturb'

    all = [
        NEW,
        WAITING_PARTNER_ANSWER,
        OK_TO_CHITCHAT,
        ASKED_TO_JOIN,
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
            trigger='ask_partner',
            source='*',
            dest=UserState.WAITING_PARTNER_ANSWER,
            after=[
                self._set_partner_id,
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
            trigger='become_asked_to_join',
            source=[
                UserState.OK_TO_CHITCHAT,
                UserState.WAITING_PARTNER_ANSWER,
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
                UserState.ASKED_TO_JOIN,
                UserState.WAITING_PARTNER_ANSWER,
            ],
            dest=UserState.OK_TO_CHITCHAT,
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

    def is_waiting_for(self, partner_id):
        if not partner_id:
            return False
        return self.state == UserState.WAITING_PARTNER_ANSWER and self.partner_id == partner_id

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
