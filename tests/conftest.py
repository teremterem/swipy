import os

import boto3
import pytest
from aioresponses import aioresponses
from boto3.resources.base import ServiceResource
from moto import mock_dynamodb2

pytest_plugins = [
    'tests.actions.data.actions_fixtures',
    'tests.actions.data.daily_co_fixtures',
    'tests.actions.data.rasa_callbacks_fixtures',
    'tests.actions.data.user_state_machine_fixtures',
    'tests.actions.data.user_vault_fixtures',
]


@pytest.fixture
def mock_aioresponses() -> aioresponses:
    with aioresponses() as m:
        yield m


@pytest.fixture(autouse=True, scope='session')
def unset_aws_profile() -> None:
    os.environ.pop('AWS_PROFILE', None)

    # delete these env vars to make sure default settings are tested
    os.environ.pop('TELL_USER_ABOUT_ERRORS', None)
    os.environ.pop('SEND_ERROR_STACK_TRACE_TO_SLOT', None)
    os.environ.pop('TELEGRAM_MSG_LIMIT_SLEEP_SEC', None)
    os.environ.pop('QUESTION_TIMEOUT_SEC', None)
    os.environ.pop('NEW_USERS_ARE_OK_TO_CHITCHAT', None)


# TODO oleksandr: how to unset env vars before any modules are imported while still using a proper fixture ?
# unset_env_vars()


@pytest.fixture
def mock_ddb() -> ServiceResource:
    with mock_dynamodb2():
        yield boto3.resource('dynamodb', os.environ['AWS_REGION'])
