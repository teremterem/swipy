import json
import os

import pytest
from boto3.resources.base import ServiceResource
from rasa.shared.core.domain import Domain
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from actions.user_state_machine import UserVault


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
def user_vault() -> UserVault:
    return UserVault()


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
        ],
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH',
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )
