import secrets
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Text, Optional, List, Type

from actions.user_state_machine import UserStateMachine


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

    @abstractmethod
    def save_user(self, user: UserStateMachine) -> None:
        raise NotImplementedError()


class NaiveUserVault(IUserVault, ABC):
    @abstractmethod
    def _get_user(self, user_id: Text) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def _list_users(self) -> List[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def save_user(self, user: UserStateMachine) -> None:
        raise NotImplementedError()

    def get_user(self, user_id: Text) -> UserStateMachine:
        user_state_machine = self._get_user(user_id)

        if user_state_machine is None:
            user_state_machine = UserStateMachine(user_id)
            self.save_user(user_state_machine)

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

    def _list_users(self) -> List[UserStateMachine]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        ddb_resp = user_state_machine_table.scan()
        return [UserStateMachine(**item) for item in ddb_resp['Items']]

    def save_user(self, user_state_machine: UserStateMachine) -> None:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        # https://stackoverflow.com/a/43672209/2040370
        user_state_machine_table.put_item(Item=asdict(user_state_machine))


UserVault: Type[IUserVault] = DdbUserVault

user_vault: IUserVault = UserVault()
