from dataclasses import dataclass
from typing import Text


class UserState:
    NEW = 'new'
    WANTS_CHITCHAT = 'wants_chitchat'
    OK_FOR_CHITCHAT = 'ok_for_chitchat'
    DO_NOT_DISTURB = 'do_not_disturb'


class UserSubState:
    ASKED_TO_JOIN = 'asked_to_join'
    WAITING_FOR_JOIN_RESPONSE = 'waiting_for_join_response'
    ASKED_FOR_READINESS = 'asked_for_readiness'
    WAITING_FOR_READINESS_RESPONSE = 'waiting_for_readiness_response'
    CHITCHAT_IN_PROGRESS = 'chitchat_in_progress'
    MAYBE_DO_NOT_DISTURB = 'maybe_do_not_disturb'
    LEAVE_ALONE_FOR_AWHILE = 'leave_alone_for_awhile'  # probably the same as maybe_do_not_disturb


@dataclass
class UserStateMachine:
    user_id: Text
    # user_uuid: Text = field(default_factory=lambda: str(uuid4()))
    state: Text = UserState.NEW
    sub_state: Text = None
    sub_state_expiration: int = None
    related_user_id: Text = None
