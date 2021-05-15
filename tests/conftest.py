import os

import boto3
import pytest
from aioresponses import aioresponses
from boto3.resources.base import ServiceResource
from moto import mock_dynamodb2

pytest_plugins = [
    "tests.actions.data.user_state_machine_fixtures",
]


@pytest.fixture
def mock_aioresponses() -> aioresponses:
    with aioresponses() as m:
        yield m


@pytest.fixture(autouse=True)
def unset_aws_profile() -> None:
    # TODO oleksandr: should I use scope='session' ?
    #  Or, maybe, some other way of ensuring that this is applied before any imports happen is needed ?
    os.environ.pop('AWS_PROFILE', None)


@pytest.fixture
def mock_ddb() -> ServiceResource:
    with mock_dynamodb2():
        yield boto3.resource('dynamodb', 'us-east-1')
