from abc import ABC, abstractmethod
from dataclasses import asdict
from decimal import Decimal
from typing import Text, Optional, List, Type, Dict, Any, Iterable

from boto3.dynamodb.conditions import Key, Attr

from actions.user_state_machine import UserStateMachine, UserState


class IUserVault(ABC):
    @abstractmethod
    def get_user(self, user_id: Text) -> UserStateMachine:
        raise NotImplementedError()

    @abstractmethod
    def get_random_available_partner(self, current_user: UserStateMachine) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def save(self, user: UserStateMachine) -> None:
        raise NotImplementedError()


class BaseUserVault(IUserVault, ABC):
    def __init__(self) -> None:
        self._user_cache = {}

    @abstractmethod
    def _get_user(self, user_id: Text) -> Optional[UserStateMachine]:
        raise NotImplementedError()

    @abstractmethod
    def _get_random_available_partner(
            self, states: Iterable[Text],
            exclude_user_id: Text,
    ) -> Optional[UserStateMachine]:
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

    def _get_random_available_partner_from_tiers(self, current_user: UserStateMachine) -> Optional[UserStateMachine]:
        for tier in UserState.chitchatable_tiers:
            partner = self._get_random_available_partner(tier, current_user.user_id)
            if partner:
                return partner
        return None

    def get_random_available_partner(self, current_user: UserStateMachine) -> Optional[UserStateMachine]:
        user = self._get_random_available_partner_from_tiers(current_user)
        if not user:
            return None

        self._user_cache[user.user_id] = user
        return user

    def save(self, user: UserStateMachine) -> None:
        self._save_user(user)
        self._user_cache[user.user_id] = user


class NaiveDdbUserVault(BaseUserVault):
    def _get_user(self, user_id: Text) -> Optional[UserStateMachine]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        ddb_resp = user_state_machine_table.get_item(
            Key={'user_id': user_id},
            # ConsistentRead=True,
        )
        item = ddb_resp.get('Item')
        return None if item is None else self._user_from_dict(item)

    def _get_random_available_partner(
            self, states: Iterable[Text],
            exclude_user_id: Text,
    ) -> Optional[UserStateMachine]:
        user_dict = self._get_random_available_partner_dict(states, exclude_user_id)
        if not user_dict:
            return None

        user = self._user_from_dict(user_dict)
        return user

    def _save_user(self, user: UserStateMachine) -> None:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        # noinspection PyDataclass
        user_dict = asdict(user)
        # https://stackoverflow.com/a/43672209/2040370
        user_state_machine_table.put_item(Item=user_dict)

    @staticmethod
    def _user_from_dict(user_dict):
        user = UserStateMachine(**user_dict)

        if isinstance(user.state_timestamp, Decimal):
            user.state_timestamp = int(user.state_timestamp)

        return user

    @staticmethod
    def _get_random_available_partner_dict(
            states: Iterable[Text],
            exclude_user_id: Text,
    ) -> List[Dict[Text, Any]]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        def item_generator():
            for state in states:
                # TODO oleksandr: parallelize ? no! we will later be switching to either Redis or Postgres anyway
                ddb_resp = user_state_machine_table.query(
                    IndexName='by_state_and_timestamp',
                    KeyConditionExpression=Key('state').eq(state),
                    FilterExpression=Attr('user_id').ne(exclude_user_id),
                    ScanIndexForward=False,
                    Limit=2,  # exclude_user_id may be selected as well (filter expression is applied AFTER limit)
                )
                items = ddb_resp.get('Items')
                if items:
                    yield items[0]

        return max(item_generator(), key=lambda i: int(i.get('state_timestamp') or 0), default=None)


UserVault: Type[IUserVault] = NaiveDdbUserVault
