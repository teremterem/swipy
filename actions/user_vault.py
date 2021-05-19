import secrets
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Text, Optional, List, Type, Dict, Any

from boto3.dynamodb.conditions import Key, Attr

from actions.user_state_machine import UserStateMachine, UserState


class IUserVault(ABC):
    @abstractmethod
    def get_user(self, user_id: Text) -> UserStateMachine:
        raise NotImplementedError()

    @abstractmethod
    def get_random_available_user(
            self, exclude_user_id: Text,
            newbie: Optional[bool] = None,
    ) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def save_user(self, user: UserStateMachine) -> None:
        raise NotImplementedError()


class NaiveUserVault(IUserVault, ABC):
    @abstractmethod
    def _get_user(self, user_id: Text) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def _list_available_user_dicts(
            self, exclude_user_id: Text,
            newbie: Optional[bool] = None,
    ) -> List[Dict[Text, Any]]:
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

    def get_random_available_user(
            self, exclude_user_id: Text,
            newbie: Optional[bool] = None,
    ) -> Optional[UserStateMachine]:
        list_of_dicts = self._list_available_user_dicts(exclude_user_id, newbie=True)
        user_dict = secrets.choice(list_of_dicts)
        return UserStateMachine(**user_dict)


class DdbUserVault(NaiveUserVault):
    def _get_user(self, user_id: Text) -> Optional[UserStateMachine]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        ddb_resp = user_state_machine_table.get_item(Key={'user_id': user_id})
        item = ddb_resp.get('Item')
        return None if item is None else UserStateMachine(**item)

    def _list_available_user_dicts(self, exclude_user_id: Text, newbie: Optional[bool] = None) -> List[Dict[Text, Any]]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        filter_expression = Attr('user_id').ne(exclude_user_id)
        if newbie is not None:
            filter_expression &= Attr('newbie').eq(newbie)

        ddb_resp = user_state_machine_table.query(
            IndexName='by_state',
            KeyConditionExpression=Key('state').eq(UserState.OK_FOR_CHITCHAT),
            FilterExpression=filter_expression,
        )
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
