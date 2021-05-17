from dataclasses import dataclass
from typing import Text

from transitions import Machine


@dataclass
class UserModel:
    user_id: Text
    state: Text = None


class UserStateMachine(UserModel):
    STATE_NEW = 'new'
    STATE_WANTS_CHITCHAT = 'wants_chitchat'
    STATE_OK_FOR_CHITCHAT = 'ok_for_chitchat'
    STATE_DO_NOT_DISTURB = 'do_not_disturb'

    STATES = [
        STATE_NEW,
        STATE_WANTS_CHITCHAT,
        STATE_OK_FOR_CHITCHAT,
        STATE_DO_NOT_DISTURB,
    ]

    def __init__(self, *args, state=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.machine = Machine(model=self, states=self.STATES, initial=self.STATE_NEW)
        if state is not None:
            self.machine.set_state(state)
