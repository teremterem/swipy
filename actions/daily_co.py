import logging
import os
from pprint import pformat
from typing import Dict, Text, Any
from urllib.parse import quote as urlencode

import aiohttp

from actions.utils import SwiperDailyCoError, current_timestamp_int

logger = logging.getLogger(__name__)

DAILY_CO_BASE_URL = os.getenv('DAILY_CO_BASE_URL', 'https://api.daily.co/v1')
DAILY_CO_API_TOKEN = os.environ['DAILY_CO_API_TOKEN']

DAILY_CO_MAX_PARTICIPANTS = int(os.getenv('DAILY_CO_MAX_PARTICIPANTS', '3'))
DAILY_CO_MEETING_DURATION_SEC = int(os.getenv('DAILY_CO_MEETING_DURATION_SEC', '1800'))  # 30 minutes (30*60 seconds)


async def create_room(sender_id: Text) -> Dict[Text, Any]:
    # TODO oleksandr: do I need to reuse ClientSession instance ? what should be its lifetime ?
    async with aiohttp.ClientSession() as session:
        room_data = {
            'privacy': 'public',
            'properties': {
                'eject_at_room_exp': True,
                'exp': current_timestamp_int() + DAILY_CO_MEETING_DURATION_SEC,
                'max_participants': DAILY_CO_MAX_PARTICIPANTS,
                'enable_network_ui': False,
                'enable_prejoin_ui': False,
                'enable_new_call_ui': True,
                'enable_screenshare': True,
                'enable_chat': True,
                'start_video_off': False,
                'start_audio_off': False,
                'owner_only_broadcast': False,
                'lang': 'en',
            },
        }
        async with session.post(
                f"{DAILY_CO_BASE_URL}/rooms",
                headers={
                    'Authorization': f"Bearer {DAILY_CO_API_TOKEN}",
                },
                json=room_data,
        ) as resp:
            resp.raise_for_status()
            resp_json = await resp.json()

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('NEW DAILY CO ROOM (sender_id=%r):\n%s', sender_id, pformat(resp_json))

    if not resp_json.get('url'):
        raise SwiperDailyCoError(repr(resp_json))

    return resp_json


async def delete_room(room_name: Text) -> Dict[Text, Any]:
    result = False
    resp_text = ''
    # noinspection PyBroadException
    try:
        # TODO oleksandr: do I need to reuse ClientSession instance ? what should be its lifetime ?
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                    f"{DAILY_CO_BASE_URL}/rooms/{urlencode(room_name)}",
                    headers={
                        'Authorization': f"Bearer {DAILY_CO_API_TOKEN}",
                    },
            ) as resp:
                resp_text = await resp.text()
                resp.raise_for_status()
                resp_json = await resp.json()

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('DAILY CO ROOM %r DELETED:\n%s', room_name, pformat(resp_json))

        result = resp_json.get('deleted') is True

    except Exception:
        logger.info(
            'Unsuccessful deletion of DAILY CO room %r:\n%s',
            room_name,
            resp_text,
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )

    return result
