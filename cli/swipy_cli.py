import os
import sys

import boto3
import click
from click import prompt

sys.path.insert(0, os.getcwd())

from actions.user_state_machine import UserState

AWS_REGION = os.environ['AWS_REGION']

dynamodb = boto3.resource('dynamodb', AWS_REGION)


@click.command()
def make_all_do_not_disturb():
    user_state_machine_table_name = prompt('Please enter the name of UserStateMachine DDB table')
    user_state_machine_table = dynamodb.Table(user_state_machine_table_name)

    counter = 0
    with user_state_machine_table.batch_writer() as writer:
        for item in user_state_machine_table.scan()['Items']:
            writer.update_item({
                'user_id': item['user_id'],
                'state': UserState.DO_NOT_DISTURB,
            })
            counter += 1
    print('DONE FOR', counter, 'ITEMS')


if __name__ == '__main__':
    make_all_do_not_disturb()
