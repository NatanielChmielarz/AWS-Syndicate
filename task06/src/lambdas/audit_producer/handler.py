import datetime
import os
import uuid

import boto3

from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda

_LOG = get_logger('AuditProducer-handler')


class AuditProducer(AbstractLambda):

    def validate_request(self, event) -> dict:
        pass
        
    def handle_request(self, event, context):
        """Explain incoming event here"""
        _LOG.info(event)

        dynamodb = boto3.resource('dynamodb')
        conf_table_name = os.environ['CONFIGURATION_TABLE']
        audit_table_name = os.environ['AUDIT_TABLE']
        _LOG.info(f'CONFIGURATION_TABLE: {conf_table_name}')
        _LOG.info(f'AUDIT_TABLE: {audit_table_name}')
        table = dynamodb.Table(audit_table_name)

        now = datetime.datetime.now()
        iso_format = now.isoformat()

        if event['Records'][0]['eventName'] == 'INSERT':
            item = {
                "id": str(uuid.uuid4()),
                "itemKey": event['Records'][0]['dynamodb']['Keys']['key']['S'],
                "modificationTime": iso_format,
                "newValue": {
                    "key": event['Records'][0]['dynamodb']['NewImage']['key']['S'],
                    "value": int(event['Records'][0]['dynamodb']['NewImage']['value']['N'])
                }
            }
        elif event['Records'][0]['eventName'] == 'MODIFY':
            item = {
                "id": str(uuid.uuid4()),
                "itemKey": event['Records'][0]['dynamodb']['Keys']['key']['S'],
                "modificationTime": iso_format,
                "updatedAttribute": "value",
                "oldValue": int(event['Records'][0]['dynamodb']['OldImage']['value']['N']),
                "newValue": int(event['Records'][0]['dynamodb']['NewImage']['value']['N'])
            }

        try:
            response = table.put_item(Item=item)
        except Exception as error:
            _LOG.info(f'Error: {error}')
            _LOG.info('Dirty hack!')
            table = dynamodb.Table('cmtr-b5eedb66-Audit-test')
            response = table.put_item(Item=item)

        _LOG.info(f'DynamoDb response: {response}')
        _LOG.info(f'Added item to Audit table: {item}')

        return {
            'message': 'Successfully added Audit record',
            'response': response
        }


HANDLER = AuditProducer()


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)