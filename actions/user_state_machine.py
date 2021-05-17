from dataclasses import dataclass
from typing import Text, Optional

from transitions import Machine


class UserState:
    NEW = 'new'
    WANTS_CHITCHAT = 'wants_chitchat'
    OK_FOR_CHITCHAT = 'ok_for_chitchat'
    DO_NOT_DISTURB = 'do_not_disturb'

    all = [
        NEW,
        WANTS_CHITCHAT,
        OK_FOR_CHITCHAT,
        DO_NOT_DISTURB,
    ]


@dataclass
class UserModel:
    user_id: Text
    state: Text = None  # the state machine will set it to UserState.NEW if not provided explicitly
    related_user_id: Optional[Text] = None


class UserStateMachine(UserModel):
    def __init__(self, *args, state=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.machine = Machine(model=self, states=UserState.all, initial=UserState.NEW)
        if state is not None:
            self.machine.set_state(state)

        self.machine.add_transition(
            trigger='request_chitchat',
            source='*',
            dest=UserState.WANTS_CHITCHAT,
            after='after_request_chitchat',
        )

    def after_request_chitchat(self):
        self.related_user_id = None
