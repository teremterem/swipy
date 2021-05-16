import logging
import os
from pprint import pformat
from typing import Text

import aiohttp

logger = logging.getLogger(__name__)

RASA_HOST = os.environ['RASA_HOST']
RASA_TOKEN = os.environ['RASA_TOKEN']


async def invite_chitchat_partner(user_id: Text, room_url: Text) -> None:
    intent_name = 'EXTERNAL_invite_chitchat_partner'

    async with aiohttp.ClientSession() as session:
        async with session.post(
                f"{RASA_HOST}/core/conversations/{user_id}/trigger_intent?output_channel=latest&token={RASA_TOKEN}",
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
