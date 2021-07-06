import json
import os
import random
import traceback
from datetime import datetime
from typing import List, Text
from unittest.mock import MagicMock, patch

import pytest
from boto3.resources.base import ServiceResource
from rasa.shared.core.domain import Domain
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions.utils import datetime_now


@pytest.fixture
def wrap_actions_datetime_now() -> MagicMock:
    _original_datetime_now = datetime_now

    def _wrap_datetime_now(*args, **kwargs) -> datetime:
        # make sure parameters don't cause the original function to crash
        # noinspection PyArgumentList
        original_result = _original_datetime_now(*args, **kwargs)
        assert isinstance(original_result, datetime)
        return datetime(2021, 5, 25)

    # TODO oleksandr: this fixture only works for actions/actions.py code - figure out how to make it more ubiquitous
    with patch('actions.actions.datetime_now') as mock_datetime_now:
        mock_datetime_now.side_effect = _wrap_datetime_now

        yield mock_datetime_now


@pytest.fixture
def wrap_traceback_format_exception() -> MagicMock:
    _original_format_exception = traceback.format_exception

    def _wrap_format_exception(*args, **kwargs) -> List[Text]:
        # make sure parameters don't cause the original function to crash
        _original_format_exception(*args, **kwargs)
        return ['stack ', 'trace ', 'goes ', 'here']

    with patch('traceback.format_exception') as mock_traceback_format_exception:
        mock_traceback_format_exception.side_effect = _wrap_format_exception

        yield mock_traceback_format_exception


@pytest.fixture
def wrap_random_randint() -> MagicMock:
    _original_randint = random.randint

    def _wrap_randint(*args, **kwargs) -> int:
        # make sure parameters don't cause the original function to crash
        _original_randint(*args, **kwargs)
        return 5 * 60 * 60  # always return 5 hours worth of seconds

    with patch('random.randint') as mock_random_randint:
        mock_random_randint.side_effect = _wrap_randint

        yield mock_random_randint


@pytest.fixture
def tracker() -> Tracker:
    """Load a tracker object"""
    with open("tests/actions/data/initial_tracker.json") as json_file:
        tracker = Tracker.from_dict(json.load(json_file))
    return tracker


@pytest.fixture
def dispatcher() -> CollectingDispatcher:
    """Create a clean dispatcher"""
    return CollectingDispatcher()


@pytest.fixture
def domain() -> DomainDict:
    """Load the domain and return it as a dictionary"""
    domain = Domain.load("domain.yml")
    return domain.as_dict()


@pytest.fixture
def create_user_state_machine_table(mock_ddb: ServiceResource) -> None:
    user_state_machine_ddb_table_name = os.environ['USER_STATE_MACHINE_DDB_TABLE']
    # noinspection PyUnresolvedReferences
    mock_ddb.create_table(
        TableName=user_state_machine_ddb_table_name,
        AttributeDefinitions=[
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S',
            },
            {
                'AttributeName': 'state',
                'AttributeType': 'S',
            },
            {
                'AttributeName': 'state_timeout_ts',
                'AttributeType': 'N',
            },
            {
                'AttributeName': 'activity_timestamp',
                'AttributeType': 'N',
            },
        ],
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH',
            },
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'by_state_and_timeout_ts',
                'KeySchema': [
                    {
                        'AttributeName': 'state',
                        'KeyType': 'HASH',
                    },
                    {
                        'AttributeName': 'state_timeout_ts',
                        'KeyType': 'RANGE',
                    },
                ],
                'Projection': {
                    'ProjectionType': 'ALL',
                },
            },
            {
                'IndexName': 'by_state_and_activity_ts',
                'KeySchema': [
                    {
                        'AttributeName': 'state',
                        'KeyType': 'HASH',
                    },
                    {
                        'AttributeName': 'activity_timestamp',
                        'KeyType': 'RANGE',
                    },
                ],
                'Projection': {
                    'ProjectionType': 'ALL',
                },
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )
