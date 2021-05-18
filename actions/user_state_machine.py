from dataclasses import dataclass
from typing import Text, Optional

from transitions import Machine


class UserState:
    NEW = 'new'
    WAITING_PARTNER_ANSWER = 'waiting_partner_answer'
    OK_FOR_CHITCHAT = 'ok_for_chitchat'
    ASKED_TO_JOIN = 'asked_to_join'
    DO_NOT_DISTURB = 'do_not_disturb'

    all = [
        NEW,
        WAITING_PARTNER_ANSWER,
        OK_FOR_CHITCHAT,
        ASKED_TO_JOIN,
        DO_NOT_DISTURB,
    ]


@dataclass
class UserModel:
    user_id: Text
    state: Text = None  # the state machine will set it to UserState.NEW if not provided explicitly
    related_user_id: Optional[Text] = None
    newbie: bool = True


class UserStateMachine(UserModel):
    def __init__(self, *args, state=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.machine = Machine(model=self, states=UserState.all, initial=UserState.NEW)
        if state is not None:
            self.machine.set_state(state)

        self.machine.add_transition(
            trigger='request_chitchat',
            source='*',
            dest=UserState.WAITING_PARTNER_ANSWER,
            after='after_request_chitchat',
        )

    def after_request_chitchat(self, related_user_id):
        self.related_user_id = related_user_id
