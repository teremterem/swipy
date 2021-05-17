from dataclasses import dataclass
from typing import Text


class UserState:
    NEW = 'new'
    WANTS_CHITCHAT = 'wants_chitchat'
    OK_FOR_CHITCHAT = 'ok_for_chitchat'
    DO_NOT_DISTURB = 'do_not_disturb'


@dataclass
class UserStateMachine:
    user_id: Text
    state: Text = UserState.NEW
