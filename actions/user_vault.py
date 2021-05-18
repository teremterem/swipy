import secrets
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Text, Optional, List, Type, Dict, Any

from actions.user_state_machine import UserStateMachine


class IUserVault(ABC):
    @abstractmethod
    def get_user(self, user_id: Text) -> UserStateMachine:
        raise NotImplementedError()

    @abstractmethod
    def get_random_available_newbie(self, exclude_user_id: Text) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def get_random_available_veteran(self, exclude_user_id: Text) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def save_user(self, user: UserStateMachine) -> None:
        raise NotImplementedError()


class NaiveUserVault(IUserVault, ABC):
    @abstractmethod
    def _get_user(self, user_id: Text) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def _list_available_user_dicts(self, exclude_user_id: Text, newbie: Optional[bool] = None) -> List[Dict[Text, Any]]:
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

    @staticmethod
    def _get_random_user(list_of_dicts: List[Dict[Text, Any]]) -> Optional[UserStateMachine]:
        user_dict = secrets.choice(list_of_dicts)
        return UserStateMachine(**user_dict)

    def get_random_available_newbie(self, exclude_user_id: Text) -> Optional[UserStateMachine]:
        return self._get_random_user(self._list_available_user_dicts(exclude_user_id, newbie=True))

    def get_random_available_veteran(self, exclude_user_id: Text) -> Optional[UserStateMachine]:
        return self._get_random_user(self._list_available_user_dicts(exclude_user_id, newbie=False))


class DdbUserVault(NaiveUserVault):
    def _get_user(self, user_id: Text) -> Optional[UserStateMachine]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        # TODO oleksandr: should I resolve the name of the field ('user_id') from the data class somehow ?
        ddb_resp = user_state_machine_table.get_item(Key={'user_id': user_id})
        item = ddb_resp.get('Item')
        return None if item is None else UserStateMachine(**item)

    def _list_available_user_dicts(self, exclude_user_id: Text, newbie: Optional[bool] = None) -> List[Dict[Text, Any]]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        # TODO TODO TODO
        ddb_resp = user_state_machine_table.scan()
        return ddb_resp['Items']

    def save_user(self, user_state_machine: UserStateMachine) -> None:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        # noinspection PyDataclass
        user_dict = asdict(user_state_machine)
        # https://stackoverflow.com/a/43672209/2040370
        user_state_machine_table.put_item(Item=user_dict)


UserVault: Type[IUserVault] = DdbUserVault

user_vault: IUserVault = UserVault()
