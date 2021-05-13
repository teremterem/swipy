import json

import pytest
from aioresponses import aioresponses
from rasa.shared.core.domain import Domain
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


@pytest.fixture
def mock_aioresponses() -> aioresponses:
    with aioresponses() as m:
        yield m


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
