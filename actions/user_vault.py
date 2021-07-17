import logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from decimal import Decimal
from pprint import pformat
from typing import Text, Optional, List, Type, Dict, Any, Iterable, Iterator

from boto3.dynamodb.conditions import Key, Attr

from actions.user_state_machine import UserStateMachine, UserState
from actions.utils import current_timestamp_int

logger = logging.getLogger(__name__)


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
            self, states: List[Text],
            current_user_id: Text,
            exclude_user_ids: List[Text],
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

        return self._cache_and_bind(user)

    def _get_random_available_partner_from_tiers(self, current_user: UserStateMachine) -> Optional[UserStateMachine]:
        exclude_user_ids = (
                [current_user.user_id] +
                (current_user.roomed_partner_ids or []) +
                (current_user.rejected_partner_ids or [])
        )

        for tier in UserState.offerable_tiers:
            partner = self._get_random_available_partner(tier, current_user.user_id, exclude_user_ids)
            if partner:
                return partner
        return None

    def get_random_available_partner(self, current_user: UserStateMachine) -> Optional[UserStateMachine]:
        user = self._get_random_available_partner_from_tiers(current_user)
        if not user:
            return None

        return self._cache_and_bind(user)

    def save(self, user: UserStateMachine) -> None:
        self._save_user(user)

        self._cache_and_bind(user)

    def _cache_and_bind(self, user: UserStateMachine):
        user._user_vault = self
        self._user_cache[user.user_id] = user
        return user


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
            self, states: List[Text],
            current_user_id: Text,
            exclude_user_ids: List[Text],
    ) -> Optional[UserStateMachine]:
        user_dict = self._get_random_available_partner_dict(states, current_user_id, exclude_user_ids)
        if not user_dict:
            return None

        user = self._user_from_dict(user_dict)
        return user

    def _save_user(self, user: UserStateMachine) -> None:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        # noinspection PyDataclass
        user_dict = asdict(user)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('SAVE USER:\n%s', pformat(user_dict))
        # https://stackoverflow.com/a/43672209/2040370
        user_state_machine_table.put_item(Item=user_dict)

    @staticmethod
    def _user_from_dict(user_dict):
        user = UserStateMachine(**user_dict)

        if isinstance(user.state_timestamp, Decimal):
            user.state_timestamp = int(user.state_timestamp)
        if isinstance(user.state_timeout_ts, Decimal):
            user.state_timeout_ts = int(user.state_timeout_ts)
        if isinstance(user.activity_timestamp, Decimal):
            user.activity_timestamp = int(user.activity_timestamp)

        return user

    @staticmethod
    def _get_random_available_partner_dict(
            states: Iterable[Text],
            current_user_id: Text,
            exclude_user_ids: List[Text],
    ) -> Optional[Dict[Text, Any]]:
        # TODO oleksandr: is there a better way to ensure that the tests have a chance to mock boto3 ?
        from actions.aws_resources import user_state_machine_table

        current_timestamp = current_timestamp_int()

        def timestamp_extractor(item: Dict[Text, Any]) -> int:
            return int(item.get('activity_timestamp') or 0)

        def filter_items(items: Iterable[Dict[Text, Any]]) -> Iterator[Dict[Text, Any]]:
            """
            While DDB FilterExpression filters by current user's excluded partners,
            this function is used to filter by potential partner's excluded partners.
            """
            return filter(
                lambda i: (
                        current_user_id not in (i.get('roomed_partner_ids') or []) and
                        current_user_id not in (i.get('rejected_partner_ids') or [])
                ),
                items,
            )

        def item_generator() -> Iterator[Dict[Text, Any]]:
            # TODO oleksandr: parallelize ? no! we will later be switching to Redis and/or Postgres anyway
            for state in states:
                if state in UserState.states_with_timeouts:
                    # TODO oleksandr: disregard the possibility of truncated item list ?
                    #  yes, we will be replacing DDB later anyways
                    ddb_resp = user_state_machine_table.query(
                        IndexName='by_state_and_timeout_ts',
                        KeyConditionExpression=Key('state').eq(state) & Key('state_timeout_ts').lt(current_timestamp),
                        FilterExpression=~Attr('user_id').is_in(exclude_user_ids),
                        ScanIndexForward=False,  # this should reduce the need to worry about truncated DDB output
                    )
                    items = ddb_resp.get('Items') or []
                    item = max(filter_items(items), key=timestamp_extractor, default=None)
                    if item:
                        yield item

                else:
                    ddb_resp = user_state_machine_table.query(
                        IndexName='by_state_and_activity_ts',
                        KeyConditionExpression=Key('state').eq(state),
                        FilterExpression=~Attr('user_id').is_in(exclude_user_ids),
                        ScanIndexForward=False,
                    )
                    items = ddb_resp.get('Items') or []
                    item = next(filter_items(items), None)
                    if item:
                        yield item

        return max(item_generator(), key=timestamp_extractor, default=None)


UserVault: Type[IUserVault] = NaiveDdbUserVault
