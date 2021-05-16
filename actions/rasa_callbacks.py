import logging
import os
from pprint import pformat
from typing import Text

import aiohttp

logger = logging.getLogger(__name__)

RASA_HOST = os.environ['RASA_HOST']
RASA_TOKEN = os.getenv('RASA_TOKEN')
RASA_CORE_PATH = os.getenv('RASA_CORE_PATH', 'core/')


async def invite_chitchat_partner(user_id: Text, room_url: Text) -> None:
    intent_name = 'EXTERNAL_invite_chitchat_partner'

    async with aiohttp.ClientSession() as session:
        params = {
            'output_channel': 'latest',
        }
        if RASA_TOKEN:
            params['token'] = RASA_TOKEN

        async with session.post(
                f"{RASA_HOST}/{RASA_CORE_PATH}conversations/{user_id}/trigger_intent",
                params=params,
                json={
                    'name': intent_name,
                    'entities': {
                        'room_link': room_url,
                    },
                },
        ) as resp:
            resp_json = await resp.json()

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('%s:\n%s', intent_name, pformat(resp_json))
