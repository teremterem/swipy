import logging
import os
from pprint import pformat
from typing import Text, Dict, Any

import aiohttp

logger = logging.getLogger(__name__)

RASA_PRODUCTION_HOST = os.environ['RASA_PRODUCTION_HOST']
RASA_TOKEN = os.getenv('RASA_TOKEN')
RASA_CORE_PATH = os.getenv('RASA_CORE_PATH', 'core/')

OUTPUT_CHANNEL = 'telegram'  # seems to be more robust than 'latest'

PARTNER_ID_SLOT = 'partner_id'
ROOM_URL_SLOT = 'room_url'


async def ask_to_join(receiver_user_id: Text, sender_user_id: Text) -> Dict[Text, Any]:
    return await _trigger_external_rasa_intent(
        receiver_user_id,
        'EXTERNAL_ask_to_join',
        {
            PARTNER_ID_SLOT: sender_user_id,
        },
    )


async def join_room(receiver_user_id: Text, sender_user_id: Text, room_url: Text) -> Dict[Text, Any]:
    return await _trigger_external_rasa_intent(
        receiver_user_id,
        'EXTERNAL_join_room',
        {
            PARTNER_ID_SLOT: sender_user_id,
            ROOM_URL_SLOT: room_url,
        },
    )


async def find_partner(receiver_user_id: Text) -> Dict[Text, Any]:
    return await _trigger_external_rasa_intent(
        receiver_user_id,
        'EXTERNAL_find_partner',
        {},
    )


async def _trigger_external_rasa_intent(
        receiver_user_id: Text,
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
                f"{RASA_PRODUCTION_HOST}/{RASA_CORE_PATH}conversations/{receiver_user_id}/trigger_intent",
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
                    '%s (\nreceiver_user_id=%r;\nentities=\n%s\n) =>\n%s',
                    intent_name,
                    receiver_user_id,
                    pformat(entities),
                    pformat(resp_json),
                )

    return resp_json
