import logging
import os
from pprint import pformat
from typing import Text, Dict, Any

import aiohttp

from actions.utils import SwiperRasaCallbackError

logger = logging.getLogger(__name__)

RASA_PRODUCTION_HOST = os.environ['RASA_PRODUCTION_HOST']
RASA_TOKEN = os.getenv('RASA_TOKEN')
RASA_CORE_PATH = os.getenv('RASA_CORE_PATH', 'core/')

OUTPUT_CHANNEL = 'telegram'  # seems to be more robust than 'latest'

PARTNER_ID_SLOT = 'partner_id'
ROOM_URL_SLOT = 'room_url'


async def ask_to_join(sender_id: Text, receiver_id: Text) -> Dict[Text, Any]:
    return await _trigger_external_rasa_intent(
        sender_id,
        receiver_id,
        'EXTERNAL_ask_to_join',
        {
            PARTNER_ID_SLOT: sender_id,
        },
    )


async def ask_if_ready(sender_id: Text, receiver_id: Text) -> Dict[Text, Any]:
    return await _trigger_external_rasa_intent(
        sender_id,
        receiver_id,
        'EXTERNAL_ask_if_ready',
        {
            PARTNER_ID_SLOT: sender_id,
        },
    )


async def join_room(sender_id: Text, receiver_id: Text, room_url: Text) -> Dict[Text, Any]:
    return await _trigger_external_rasa_intent(
        sender_id,
        receiver_id,
        'EXTERNAL_join_room',
        {
            PARTNER_ID_SLOT: sender_id,
            ROOM_URL_SLOT: room_url,
        },
    )


async def join_room_ready(sender_id: Text, receiver_id: Text, room_url: Text) -> Dict[Text, Any]:
    return await _trigger_external_rasa_intent(
        sender_id,
        receiver_id,
        'EXTERNAL_join_room_ready',
        {
            PARTNER_ID_SLOT: sender_id,
            ROOM_URL_SLOT: room_url,
        },
    )


async def find_partner(sender_id: Text, receiver_id: Text) -> Dict[Text, Any]:
    return await _trigger_external_rasa_intent(
        sender_id,
        receiver_id,
        'EXTERNAL_find_partner',
        {},
    )


async def report_unavailable(sender_id: Text, receiver_id: Text) -> Dict[Text, Any]:
    return await _trigger_external_rasa_intent(
        sender_id,
        receiver_id,
        'EXTERNAL_report_unavailable',
        {},
    )


async def _trigger_external_rasa_intent(
        sender_id: Text,
        receiver_id: Text,
        intent_name: Text,
        entities: Dict[Text, Text],
) -> Dict[Text, Any]:
    # TODO oleksandr: do I need to reuse ClientSession instance ? what should be its lifetime ?
    async with aiohttp.ClientSession() as session:
        params = {
            'output_channel': OUTPUT_CHANNEL,
        }
        if RASA_TOKEN:
            params['token'] = RASA_TOKEN

        async with session.post(
                f"{RASA_PRODUCTION_HOST}/{RASA_CORE_PATH}conversations/{receiver_id}/trigger_intent",
                params=params,
                json={
                    'name': intent_name,
                    'entities': entities,
                },
        ) as resp:
            resp_json = await resp.json()

    # TODO oleksandr: change log level back to DEBUG when you decide how to identify and react to failures
    if logger.isEnabledFor(logging.INFO):
        logger.info(
            'TRIGGER_INTENT %r RESULT:\n\nSENDER_ID: %r\n\nRECEIVER_ID: %r\n\nENTITIES:\n%s\n\nRESPONSE:\n%s',
            intent_name,
            sender_id,
            receiver_id,
            pformat(entities),
            pformat(resp_json),
        )

    if not resp_json.get('tracker') or resp_json.get('status') == 'failure':
        raise SwiperRasaCallbackError(repr(resp_json))

    return resp_json
