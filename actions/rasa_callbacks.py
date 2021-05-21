import logging
import os
from pprint import pformat
from typing import Text

import aiohttp

logger = logging.getLogger(__name__)

RASA_PRODUCTION_HOST = os.environ['RASA_PRODUCTION_HOST']
RASA_TOKEN = os.getenv('RASA_TOKEN')
RASA_CORE_PATH = os.getenv('RASA_CORE_PATH', 'core/')

OUTPUT_CHANNEL = 'telegram'  # seems to be more robust than 'latest'

PARTNER_ID_ENTITY = 'partner_id'


async def ask_to_join(receiver_id: Text, asker_id: Text) -> None:
    return await _trigger_external_rasa_intent(
        receiver_id,
        'EXTERNAL_ask_to_join',
        partner_id=asker_id,
    )


async def invite_chitchat_partner(user_id: Text, room_url: Text) -> None:
    return await _trigger_external_rasa_intent(
        user_id,
        'EXTERNAL_invite_chitchat_partner',
        room_link=room_url,
    )


async def _trigger_external_rasa_intent(
        receiver_user_id: Text,
        intent_name: Text,
        **entities: Text,
):
    async with aiohttp.ClientSession() as session:  # TODO oleksandr: do I need to cache/reuse these sessions ?
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

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('%s:\n%s', intent_name, pformat(resp_json))

    return resp_json
