import secrets
from typing import Text, Optional


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


class UserStateMachine:
    def __init__(self, user_id: Text) -> None:
        self.user_id = user_id
        self.state = UserState.NEW
        self.sub_state = None
        self.sub_state_expiration = None
        self.related_user_id = None


class _InMemoryUserVault:
    def __init__(self) -> None:
        self._users = {}

    def get_user(self, user_id: Text) -> UserStateMachine:
        user_state_machine = self._users.get(user_id)

        if user_state_machine is None:
            user_state_machine = UserStateMachine(user_id)
            self._users[user_id] = user_state_machine

        return user_state_machine

    def get_random_user(self) -> Optional[UserStateMachine]:
        if not self._users:
            return None
        return secrets.choice(list(self._users.values()))

    def get_random_available_user(self, current_user_id: Text) -> Optional[UserStateMachine]:
        return None


UserVault = _InMemoryUserVault

user_vault = UserVault()
