import os

import boto3

AWS_REGION = os.environ['AWS_REGION']
USER_STATE_MACHINE_DDB_TABLE = os.environ['USER_STATE_MACHINE_DDB_TABLE']

dynamodb = boto3.resource('dynamodb', AWS_REGION)
user_state_machine_table = dynamodb.Table(USER_STATE_MACHINE_DDB_TABLE)
