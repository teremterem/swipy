import re
from typing import Dict, Text, Any, Callable, Tuple
from unittest.mock import patch, AsyncMock

import pytest
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from yarl import URL

from actions import rasa_callbacks
from actions.user_state_machine import UserStateMachine
from actions.utils import SwiperRasaCallbackError


@pytest.mark.asyncio
@patch('actions.rasa_callbacks._trigger_external_rasa_intent', wraps=rasa_callbacks._trigger_external_rasa_intent)
async def test_ask_to_join(
        wrap_trigger_external_rasa_intent: AsyncMock,
        rasa_callbacks_expected_req_builder: Callable[
            [Text, Text, Dict[Text, Any]], Tuple[Tuple[Text, URL], RequestCall]
        ],
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> None:
    expected_req_key, expected_req_call = rasa_callbacks_expected_req_builder(
        'partner_id_to_ask',
        'EXTERNAL_ask_to_join',
        {
            'partner_id': 'id_of_asker',
            'partner_photo_file_id': 'photo_of_the_asker',
        },
    )
    mock_aioresponses.post(re.compile(r'.*'), payload=external_intent_response)

    assert await rasa_callbacks.ask_to_join(
        'id_of_asker',
        UserStateMachine(user_id='partner_id_to_ask'),
        'photo_of_the_asker',
    ) == external_intent_response

    assert mock_aioresponses.requests == {expected_req_key: [expected_req_call]}
    wrap_trigger_external_rasa_intent.assert_called_once_with(
        'id_of_asker',
        UserStateMachine(user_id='partner_id_to_ask'),
        'EXTERNAL_ask_to_join',
        {
            'partner_id': 'id_of_asker',
            'partner_photo_file_id': 'photo_of_the_asker',
        },
        False,  # make sure errors are not suppressed by default
    )


@pytest.mark.asyncio
@patch('actions.rasa_callbacks._trigger_external_rasa_intent', wraps=rasa_callbacks._trigger_external_rasa_intent)
async def test_join_room(
        wrap_trigger_external_rasa_intent: AsyncMock,
        rasa_callbacks_expected_req_builder: Callable[
            [Text, Text, Dict[Text, Any]], Tuple[Tuple[Text, URL], RequestCall]
        ],
        mock_aioresponses: aioresponses,
        external_intent_response: Dict[Text, Any],
) -> None:
    expected_req_key, expected_req_call = rasa_callbacks_expected_req_builder(
        'a_receiving_user',
        'EXTERNAL_join_room',
        {
            'partner_id': 'a_sending_user',
            'room_url': 'https://room-unittest/url',
        },
    )
    mock_aioresponses.post(re.compile(r'.*'), payload=external_intent_response)

    assert await rasa_callbacks.join_room(
        'a_sending_user',
        UserStateMachine(user_id='a_receiving_user'),
        'https://room-unittest/url',
    ) == external_intent_response

    assert mock_aioresponses.requests == {expected_req_key: [expected_req_call]}
    wrap_trigger_external_rasa_intent.assert_called_once_with(
        'a_sending_user',
        UserStateMachine(user_id='a_receiving_user'),
        'EXTERNAL_join_room',
        {
            'partner_id': 'a_sending_user',
            'room_url': 'https://room-unittest/url',
        },
        False,  # make sure errors are not suppressed by default
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('suppress_callback_errors', [True, False])
@pytest.mark.parametrize('unsuccessful_response', [
    {'no_tracker': 'here'},
    {'tracker': None},
    {'tracker': {}},
    {
        'tracker': {'is': 'here, but'},
        'status': 'failure',
    },
])
async def test_callback_unsuccessful(
        rasa_callbacks_expected_req_builder: Callable[
            [Text, Text, Dict[Text, Any]], Tuple[Tuple[Text, URL], RequestCall]
        ],
        mock_aioresponses: aioresponses,
        unsuccessful_response: Dict[Text, Any],
        suppress_callback_errors: bool,
) -> None:
    expected_req_key, expected_req_call = rasa_callbacks_expected_req_builder(
        'a_receiving_user',
        'EXTERNAL_intent',
        {'some_entity': 'entity_value'},
    )
    mock_aioresponses.post(re.compile(r'.*'), payload=unsuccessful_response)

    if suppress_callback_errors:
        result = await rasa_callbacks._trigger_external_rasa_intent(
            'some_sender_id',
            UserStateMachine(user_id='a_receiving_user'),
            'EXTERNAL_intent',
            {'some_entity': 'entity_value'},
            suppress_callback_errors,
        )
        assert result is None  # we are not returning anything if errors are suppressed
    else:
        with pytest.raises(SwiperRasaCallbackError):
            await rasa_callbacks._trigger_external_rasa_intent(
                'some_sender_id',
                UserStateMachine(user_id='a_receiving_user'),
                'EXTERNAL_intent',
                {'some_entity': 'entity_value'},
                suppress_callback_errors,
            )
    assert mock_aioresponses.requests == {expected_req_key: [expected_req_call]}
