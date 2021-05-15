import boto3

# TODO oleksandr: read from env vars ?

dynamodb = boto3.resource('dynamodb', 'us-east-1')

user_state_machine_table = dynamodb.Table('UserStateMachine')
