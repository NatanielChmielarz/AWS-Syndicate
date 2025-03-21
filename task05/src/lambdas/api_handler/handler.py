import datetime
import json
import os
import uuid
import boto3
from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda

_LOG = get_logger("ApiHandler-handler")


class ApiHandler(AbstractLambda):
    def validate_request(self, event) -> dict:
        pass

    def handle_request(self, event, context):
        """
        Process the incoming event and store it in DynamoDB.
        """
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        item = {
            "id": str(uuid.uuid4()),
            "principalId": event.get("principalId", 1),
            "createdAt": timestamp,
            "body": event.get("content", {}),
        }
        
        _LOG.info("Saving item: %s", item)

        dynamodb = boto3.resource("dynamodb", region_name=os.getenv("region", "eu-central-1"))
        table = dynamodb.Table(os.getenv("table_name", "Events"))
        
        response = table.put_item(Item=item)
        
        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response, indent=4),
        }


HANDLER = ApiHandler()

def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)