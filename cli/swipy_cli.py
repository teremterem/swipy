import asyncio
import os
import sys
import time
from dataclasses import asdict
from pprint import pprint
from typing import Text, Any

import boto3
import click
from click import prompt

sys.path.insert(0, os.getcwd())

from actions.user_state_machine import UserState, UserStateMachine

AWS_REGION = os.environ['AWS_REGION']

dynamodb = boto3.resource('dynamodb', AWS_REGION)


def _prompt_ddb_table() -> Any:
    user_state_machine_table_name = prompt('Please enter the name of UserStateMachine DDB table')
    if prompt('Once again please') != user_state_machine_table_name:
        raise ValueError('DDB table name differs')

    user_state_machine_table = dynamodb.Table(user_state_machine_table_name)
    return user_state_machine_table


def _set_everyones_state(state: Text) -> None:
    user_state_machine_table = _prompt_ddb_table()

    counter = 0
    for item in user_state_machine_table.scan()['Items']:
        user_state_machine_table.update_item(
            Key={'user_id': item['user_id']},
            UpdateExpression='set #state=:state',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={':state': state},
        )
        counter += 1
        if counter % 10 == 0:
            print(counter)
    print('DONE FOR', counter, 'ITEMS')


@click.group()
def swipy() -> None:
    ...


@swipy.command()
def make_everyone_available_to_everyone() -> None:
    user_state_machine_table = _prompt_ddb_table()

    counter = 0
    for item in user_state_machine_table.scan()['Items']:
        user_state_machine_table.update_item(
            Key={'user_id': item['user_id']},
            UpdateExpression='REMOVE #room, #roomed, #rejected, #seen SET #state=:state',
            ExpressionAttributeNames={
                '#room': 'latest_room_name',
                '#roomed': 'roomed_partner_ids',
                '#rejected': 'rejected_partner_ids',
                '#seen': 'seen_partner_ids',
                '#state': 'state',
            },
            ExpressionAttributeValues={':state': UserState.OK_TO_CHITCHAT},
        )
        counter += 1
        if counter % 10 == 0:
            print(counter)
    print('DONE FOR', counter, 'ITEMS')


@swipy.command()
def make_everyone_do_not_disturb() -> None:
    _set_everyones_state(UserState.DO_NOT_DISTURB)


@swipy.command()
def make_everyone_ok_to_chitchat() -> None:
    _set_everyones_state(UserState.OK_TO_CHITCHAT)


@swipy.command()
def start_everyone() -> None:
    user_state_machine_table = _prompt_ddb_table()

    class DummyUserVault:
        def save(self, user: UserStateMachine) -> None:
            # noinspection PyDataclass
            user_state_machine_table.put_item(Item=asdict(user))

    dummy_user_vault = DummyUserVault()

    os.environ['RASA_PRODUCTION_HOST'] = prompt('RASA_PRODUCTION_HOST')
    rasa_token = prompt('RASA_TOKEN (type "none" if none)')
    if rasa_token != 'none':
        os.environ['RASA_TOKEN'] = rasa_token

    from actions import rasa_callbacks

    async def do_callbacks():
        counter = 0
        for item in user_state_machine_table.scan()['Items']:
            print(item.get('user_id'))
            pprint(item.get('telegram_from'))

            # noinspection PyProtectedMember,PyTypeChecker
            await rasa_callbacks._trigger_external_rasa_intent(
                'script',
                UserStateMachine(**item, user_vault=dummy_user_vault),
                'start',  # TODO oleksandr: support another, special "start" intent that does not update activity_ts
                {},
                True,
            )
            counter += 1
            print()
            time.sleep(1.1)
        print('DONE FOR', counter, 'ITEMS')

    asyncio.run(do_callbacks())


if __name__ == '__main__':
    swipy()
