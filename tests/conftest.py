import os

import boto3
import pytest
from aioresponses import aioresponses
from boto3.resources.base import ServiceResource
from moto import mock_dynamodb2

pytest_plugins = [
    'tests.actions.data.daily_co_fixtures',
    'tests.actions.data.rasa_callbacks_fixtures',
    'tests.actions.data.telegram_helpers_fixtures',
    'tests.actions.data.user_state_machine_fixtures',
    'tests.actions.data.user_vault_fixtures',
]


# noinspection PyUnusedLocal
def pytest_configure(*args, **kwargs) -> None:
    """unset certain env vars before any modules are imported"""
    os.environ.pop('AWS_PROFILE', None)

    # delete these env vars to make sure default settings are tested
    os.environ.pop('TELL_USER_ABOUT_ERRORS', None)
    os.environ.pop('SEND_ERROR_STACK_TRACE_TO_SLOT', None)
    os.environ.pop('DAILY_CO_MAX_PARTICIPANTS', None)
    os.environ.pop('DAILY_CO_MEETING_DURATION_SEC', None)
    os.environ.pop('CLEAR_REJECTED_LIST_WHEN_NO_ONE_FOUND', None)
    os.environ.pop('FIND_PARTNER_FREQUENCY_SEC', None)
    os.environ.pop('PARTNER_CONFIRMATION_TIMEOUT_SEC', None)
    os.environ.pop('SHORT_BREAK_TIMEOUT_SEC', None)
    os.environ.pop('PARTNER_SEARCH_TIMEOUT_SEC', None)
    os.environ.pop('SWIPER_STATE_MIN_TIMEOUT_SEC', None)
    os.environ.pop('SWIPER_STATE_MAX_TIMEOUT_SEC', None)
    os.environ.pop('GREETING_MAKES_USER_OK_TO_CHITCHAT', None)
    os.environ.pop('SEARCH_CANCELLATION_TAKES_A_BREAK', None)
    os.environ.pop('WAITING_CANCELLATION_REJECTS_INVITATION', None)
    os.environ.pop('NUM_OF_ROOMED_PARTNERS_TO_REMEMBER', None)
    os.environ.pop('NUM_OF_REJECTED_PARTNERS_TO_REMEMBER', None)
    os.environ.pop('NUM_OF_SEEN_PARTNERS_TO_REMEMBER', None)


pytest_configure()  # TODO oleksandr: is this a bad practice ? why ?


@pytest.fixture
def mock_aioresponses() -> aioresponses:
    with aioresponses() as m:
        yield m


@pytest.fixture
def mock_ddb() -> ServiceResource:
    with mock_dynamodb2():
        yield boto3.resource('dynamodb', os.environ['AWS_REGION'])
