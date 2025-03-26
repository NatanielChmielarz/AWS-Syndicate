from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda
import boto3
import json
import uuid
import os
from decimal import Decimal
from datetime import datetime

_LOG = get_logger('ApiHandler-handler')

class ApiHandler(AbstractLambda):
    def __init__(self):
        self.client = boto3.client('cognito-idp')
        self.dynamodb = boto3.resource('dynamodb')
        self.user_pool_id = self.get_user_pool_id()
        self.client_app_id = self.get_client_app_id()
        self.tables_table = self.dynamodb.Table(os.environ['TABLES'])
        self.reservations_table = self.dynamodb.Table(os.environ['RESERVATIONS'])

    def get_user_pool_id(self):
        user_pool_name = os.environ['USER_POOL']
        response = self.client.list_user_pools(MaxResults=60)
        for user_pool in response['UserPools']:
            if user_pool['Name'] == user_pool_name:
                return user_pool['Id']
        return None

    def get_client_app_id(self):
        response = self.client.list_user_pool_clients(UserPoolId=self.user_pool_id)
        for user_pool_client in response['UserPoolClients']:
            if user_pool_client['ClientName'] == 'client-app':
                return user_pool_client['ClientId']
        return None

    def decimal_serializer(self, obj):
        if isinstance(obj, Decimal):
            return int(obj)
        raise TypeError("Type not serializable")

    def handle_request(self, event, context):
        path = event['path']
        http_method = event['httpMethod']
        _LOG.info(f'{path} {http_method}')

        try:
            if path == '/signup' and http_method == 'POST':
                return self.signup(json.loads(event['body']))
            elif path == '/signin' and http_method == 'POST':
                return self.signin(json.loads(event['body']))
            elif path == '/tables' and http_method == 'GET':
                return self.get_tables()
            elif path == '/tables' and http_method == 'POST':
                return self.create_table(json.loads(event['body']))
            elif event['resource'] == '/tables/{tableId}' and http_method == 'GET':
                return self.get_table(event)
            elif path == '/reservations' and http_method == 'GET':
                return self.get_reservations()
            elif path == '/reservations' and http_method == 'POST':
                return self.create_reservation(json.loads(event['body']))
        except Exception as e:
            _LOG.error(f'Error: {e}')
            return {'statusCode': 400, 'body': json.dumps({'message': 'Something went wrong'})}

    def signup(self, body):
        response = self.client.admin_create_user(
            UserPoolId=self.user_pool_id,
            Username=body['email'],
            UserAttributes=[
                {'Name': 'email', 'Value': body['email']},
                {'Name': 'given_name', 'Value': body['firstName']},
                {'Name': 'family_name', 'Value': body['lastName']}
            ],
            TemporaryPassword=body['password'],
            MessageAction='SUPPRESS'
        )
        self.client.admin_set_user_password(
            UserPoolId=self.user_pool_id,
            Username=body['email'],
            Password=body['password'],
            Permanent=True
        )
        return {'statusCode': 200, 'body': json.dumps({'message': 'Sign-up successful'})}

    def signin(self, body):
        response = self.client.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={'USERNAME': body['email'], 'PASSWORD': body['password']},
            ClientId=self.client_app_id
        )
        return {'statusCode': 200, 'body': json.dumps({'accessToken': response['AuthenticationResult']['IdToken']})}

    def get_tables(self):
        response = self.tables_table.scan()
        return {'statusCode': 200, 'body': json.dumps({'tables': sorted(response['Items'], key=lambda item: item['id'])}, default=self.decimal_serializer)}

    def create_table(self, body):
        item = {"id": int(body['id']), "number": body['number'], "places": body['places'], "isVip": body['isVip'], "minOrder": body['minOrder']}
        self.tables_table.put_item(Item=item)
        return {'statusCode': 200, 'body': json.dumps({'id': body['id']})}

    def get_table(self, event):
        table_id = int(event['path'].split('/')[-1])
        item = self.tables_table.get_item(Key={'id': table_id})
        return {'statusCode': 200, 'body': json.dumps(item['Item'], default=self.decimal_serializer)}

    def get_reservations(self):
        response = self.reservations_table.scan()
        for item in response['Items']:
            del item['id']
        return {'statusCode': 200, 'body': json.dumps({'reservations': sorted(response['Items'], key=lambda item: item['tableNumber'])}, default=self.decimal_serializer)}

    def create_reservation(self, body):
        tables = {table['number'] for table in self.tables_table.scan()['Items']}
        if body['tableNumber'] not in tables:
            raise ValueError("No such table.")

        proposed_start = datetime.strptime(body["slotTimeStart"], "%H:%M").time()
        proposed_end = datetime.strptime(body["slotTimeEnd"], "%H:%M").time()

        reservations = self.reservations_table.scan()['Items']
        for res in reservations:
            if res['tableNumber'] == body['tableNumber'] and res['date'] == body['date']:
                res_start = datetime.strptime(res["slotTimeStart"], "%H:%M").time()
                res_end = datetime.strptime(res["slotTimeEnd"], "%H:%M").time()
                if any(res_start <= t <= res_end for t in (proposed_start, proposed_end)):
                    raise ValueError('Time already reserved')

        reservation_id = str(uuid.uuid4())
        self.reservations_table.put_item(Item={"id": reservation_id, **body})
        return {'statusCode': 200, 'body': json.dumps({'reservationId': reservation_id})}

HANDLER = ApiHandler()

def lambda_handler(event, context):
    return HANDLER.handle_request(event, context)