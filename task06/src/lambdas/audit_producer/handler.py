import os

from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda
import boto3
import uuid
from datetime import datetime, timezone

_LOG = get_logger(__name__)


class AuditProducer(AbstractLambda):

    def validate_request(self, event) -> dict:
        pass

    def handle_request(self, event, context):
        """
        Explain incoming event here
        """
        dynamodb = boto3.resource("dynamodb")
        table_name = os.getenv('table_name')

        audit_table = dynamodb.Table(table_name)

        conf_item = event.get("Records")[0]
        audit_item = None
        if conf_item["eventName"] == "INSERT":
            audit_item = {"id": str(uuid.uuid4()),
                          "itemKey": conf_item["dynamodb"]["NewImage"]["key"]["S"],
                          "modificationTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                          "newValue": {
                              "key": conf_item["dynamodb"]["NewImage"]["key"]["S"],
                              "value": int(conf_item["dynamodb"]["NewImage"]["value"]["N"])
                          },
                          }
        elif conf_item["eventName"] == "MODIFY":
            audit_item = {"id": str(uuid.uuid4()),
                          "itemKey": conf_item["dynamodb"]["NewImage"]["key"]["S"],
                          "modificationTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                          "updatedAttribute": "value",
                          "oldValue": int(conf_item["dynamodb"]["OldImage"]["value"]["N"]),
                          "newValue": int(conf_item["dynamodb"]["NewImage"]["value"]["N"])
                          }

        audit_table.put_item(Item=audit_item)


HANDLER = AuditProducer()


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)

 