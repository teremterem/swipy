import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Text, Optional, List


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


class IUserVault(ABC):
    @abstractmethod
    def get_user(self, user_id: Text) -> UserStateMachine:
        raise NotImplementedError()

    @abstractmethod
    def get_random_user(self) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def get_random_available_user(self, current_user_id: Text) -> Optional[UserStateMachine]:
        raise NotImplementedError()


class NaiveUserVault(IUserVault, ABC):
    @abstractmethod
    def _get_user(self, user_id: Text) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def _put_user(self, user_state_machine: UserStateMachine) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _list_users(self) -> List[UserStateMachine]:
        raise NotImplementedError()

    def get_user(self, user_id: Text) -> UserStateMachine:
        user_state_machine = self._get_user(user_id)

        if user_state_machine is None:
            user_state_machine = UserStateMachine(user_id)
            self._put_user(user_state_machine)

        return user_state_machine

    def get_random_user(self) -> Optional[UserStateMachine]:
        user_list = self._list_users()
        if not user_list:
            return None
        return secrets.choice(user_list)

    def get_random_available_user(self, current_user_id: Text) -> Optional[UserStateMachine]:
        for _ in range(10):
            user_state_machine = self.get_random_user()

            if user_state_machine.user_id == current_user_id:
                continue

            return user_state_machine

        return None


class DdbUserVault(NaiveUserVault):
    def _get_user(self, user_id: Text) -> Optional[UserStateMachine]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        # TODO oleksandr: should I resolve the name of the field ('user_id') from the data class somehow ?
        ddb_resp = user_state_machine_table.get_item(Key={'user_id': user_id})
        item = ddb_resp.get('Item')
        return None if item is None else UserStateMachine(**item)

    def _put_user(self, user_state_machine: UserStateMachine) -> None:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        user_state_machine_table.put_item(Item=asdict(user_state_machine))

    def _list_users(self) -> List[UserStateMachine]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        ddb_resp = user_state_machine_table.scan()
        return [UserStateMachine(**item) for item in ddb_resp['Items']]


UserVault = DdbUserVault

user_vault: IUserVault = UserVault()
