import os
import sys
from typing import Text

import boto3
import click
from click import prompt

sys.path.insert(0, os.getcwd())

from actions.user_state_machine import UserState

AWS_REGION = os.environ['AWS_REGION']

dynamodb = boto3.resource('dynamodb', AWS_REGION)


def _set_everyones_state(state: Text) -> None:
    user_state_machine_table_name = prompt('Please enter the name of UserStateMachine DDB table')
    if prompt('Once again please') != user_state_machine_table_name:
        raise ValueError('DDB table name differs')

    user_state_machine_table = dynamodb.Table(user_state_machine_table_name)

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
def make_everyone_do_not_disturb() -> None:
    _set_everyones_state(UserState.DO_NOT_DISTURB)


@swipy.command()
def make_everyone_ok_to_chitchat() -> None:
    _set_everyones_state(UserState.OK_TO_CHITCHAT)


if __name__ == '__main__':
    swipy()
