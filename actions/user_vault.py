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
    def save(self, user: UserStateMachine) -> None:
        raise NotImplementedError()


class NaiveUserVault(IUserVault, ABC):
    def __init__(self) -> None:
        self._user_cache = {}

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
    def _save_user(self, user: UserStateMachine) -> None:
        raise NotImplementedError()

    def get_user(self, user_id: Text) -> UserStateMachine:
        """
        Unlike `_get_user`, this method creates the user if the user does not exist yet
        (as well as relies on a so called first level cache when the same user is requested multiple times).
        """
        if not user_id:
            raise ValueError('user_id cannot be empty')

        user = self._user_cache.get(user_id)
        # we are relying on None instead of a sentinel object to test if it is a miss
        # because get_user is never expected to return None anyways
        if user is not None:
            return user

        user = self._get_user(user_id)

        if user is None:
            user = UserStateMachine(user_id)
            self._save_user(user)

        self._user_cache[user_id] = user
        return user

    def get_random_available_user(
            self, exclude_user_id: Text,
            newbie: Optional[bool] = None,
    ) -> Optional[UserStateMachine]:
        list_of_dicts = self._list_available_user_dicts(exclude_user_id, newbie=newbie)
        if not list_of_dicts:
            return None

        user_dict = secrets.choice(list_of_dicts)
        user = UserStateMachine(**user_dict)

        self._user_cache[user.user_id] = user
        return user

    def save(self, user: UserStateMachine) -> None:
        self._save_user(user)
        self._user_cache[user.user_id] = user


class NaiveDdbUserVault(NaiveUserVault):
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
            KeyConditionExpression=Key('state').eq(UserState.OK_TO_CHITCHAT),
            FilterExpression=filter_expression,
        )
        return ddb_resp.get('Items', [])

    def _save_user(self, user: UserStateMachine) -> None:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        # noinspection PyDataclass
        user_dict = asdict(user)
        # https://stackoverflow.com/a/43672209/2040370
        user_state_machine_table.put_item(Item=user_dict)


UserVault: Type[IUserVault] = NaiveDdbUserVault
