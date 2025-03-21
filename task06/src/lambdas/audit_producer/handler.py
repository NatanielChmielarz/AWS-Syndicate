from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda

_LOG = get_logger("AuditProducer-handler")

import os
import uuid
import boto3
from datetime import datetime


class AuditProducer(AbstractLambda):

    def validate_request(self, event) -> dict:
        pass

    def handle_request(self, event, context):
        """
        Explain incoming event here
        """
        _LOG.info("Event:\n%s", str(event))

        for entry in event["Records"]:
            if entry["eventName"] == "INSERT":
                self.process_insert(entry["dynamodb"])
            elif entry["eventName"] == "MODIFY":
                self.process_update(entry["dynamodb"])

    def process_insert(self, dynamodb_entry):
        _LOG.info("Executing process_insert method")
        new_entry_snapshot = dynamodb_entry["NewImage"]

        dynamodb_resource = boto3.resource("dynamodb")
        audit_db_table = dynamodb_resource.Table(
            os.environ.get("AUDIT_TABLE_NAME", "Audit")
        )

        audit_record = {
            "auditId": str(uuid.uuid4()),
            "recordKey": new_entry_snapshot["key"]["S"],
            "timestamp": datetime.utcnow().isoformat(),
            "newData": {
                "key": new_entry_snapshot["key"]["S"],
                "value": int(new_entry_snapshot["value"]["N"]),
            },
        }

        response = audit_db_table.put_item(Item=audit_record)
        _LOG.info(response)

    def process_update(self, dynamodb_entry):
        _LOG.info("Executing process_update method")

        previous_entry_snapshot = dynamodb_entry["OldImage"]
        new_entry_snapshot = dynamodb_entry["NewImage"]

        dynamodb_resource = boto3.resource("dynamodb")
        audit_db_table = dynamodb_resource.Table(
            os.environ.get("AUDIT_TABLE_NAME", "Audit")
        )

        if previous_entry_snapshot["value"]["N"] != new_entry_snapshot["value"]["N"]:
            audit_record = {
                "auditId": str(uuid.uuid4()),
                "recordKey": new_entry_snapshot["key"]["S"],
                "timestamp": datetime.now().isoformat(),
                "modifiedField": "value",
                "previousValue": int(previous_entry_snapshot["value"]["N"]),
                "updatedValue": int(new_entry_snapshot["value"]["N"]),
            }

            response = audit_db_table.put_item(Item=audit_record)
            _LOG.info(response)


HANDLER = AuditProducer()


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)
