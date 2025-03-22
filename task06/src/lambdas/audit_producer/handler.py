import os
import uuid
from datetime import datetime
import boto3

from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda

_LOGGER = get_logger('AuditLogger')

dynamodb_resource = boto3.resource('dynamodb')
AUDIT_LOG_TABLE = os.environ.get('audit_log_table', 'AuditLog')


class DynamoDBAuditHandler(AbstractLambda):

    def validate_event(self, event) -> dict:
        return event

    def process_event(self, event, context):
        """
        Processes incoming DynamoDB stream events and logs changes into an audit table.
        """
        audit_table = dynamodb_resource.Table(AUDIT_LOG_TABLE)
        _LOGGER.info(f"Processing event: {event}, context: {context}")
        
        event_records = event.get('Records', [])
        if not event_records:
            _LOGGER.debug("No records to process.")
            return 200
        
        for record in event_records:
            try:
                event_type = record.get('eventName')
                db_record = record.get('dynamodb', {})
                _LOGGER.info(f"Handling event type: {event_type}, data: {db_record}")
                
                primary_keys = convert_dynamodb_json(db_record.get('Keys', {}))
                record_id = primary_keys.get('key')
                if not record_id:
                    _LOGGER.error(f"Missing 'key' in record keys: {primary_keys}")
                    continue

                timestamp = datetime.now().isoformat()

                if event_type == 'INSERT':
                    new_record = convert_dynamodb_json(db_record.get('NewImage', {}))
                    _LOGGER.info(f"New record data: {new_record}")
                    
                    audit_entry = {
                        "entryId": str(uuid.uuid4()),
                        "recordId": record_id,
                        "timestamp": timestamp,
                        "newData": new_record
                    }
                    audit_table.put_item(Item=audit_entry)
                    _LOGGER.info(f"Logged INSERT event for recordId={record_id}")

                elif event_type == 'MODIFY':
                    new_record = convert_dynamodb_json(db_record.get('NewImage', {}))
                    old_record = convert_dynamodb_json(db_record.get('OldImage', {}))

                    for field, new_value in new_record.items():
                        old_value = old_record.get(field)
                        if old_value != new_value:
                            audit_entry = {
                                "entryId": str(uuid.uuid4()),
                                "recordId": record_id,
                                "timestamp": timestamp,
                                "modifiedField": field,
                                "previousValue": old_value,
                                "updatedValue": new_value
                            }
                            audit_table.put_item(Item=audit_entry)
                            _LOGGER.info(f"Logged MODIFY event for recordId={record_id}, field={field}")
            
            except Exception as error:
                _LOGGER.error(f"Error processing record: {record}. Exception: {error}")
                continue
        
        return 200


AUDIT_HANDLER = DynamoDBAuditHandler()

def lambda_handler(event, context):
    _LOGGER.info(f"Lambda triggered with event: {event}")
    try:
        return AUDIT_HANDLER.process_event(event=event, context=context)
    except Exception as error:
        _LOGGER.error(f"Unhandled exception in lambda_handler: {error}")


def convert_dynamodb_json(dynamo_json):
    """
    Converts DynamoDB JSON structure to a standard Python dictionary.
    """
    if isinstance(dynamo_json, dict):
        parsed_result = {}
        for key, val in dynamo_json.items():
            if isinstance(val, dict):
                if "S" in val:
                    parsed_result[key] = val["S"]
                elif "N" in val:
                    parsed_result[key] = int(val["N"]) if "." not in val["N"] else float(val["N"])
                elif "M" in val:
                    parsed_result[key] = convert_dynamodb_json(val["M"])
                elif "L" in val:
                    parsed_result[key] = [convert_dynamodb_json(item) for item in val["L"]]
            else:
                parsed_result[key] = val
        return parsed_result
    elif isinstance(dynamo_json, list):
        return [convert_dynamodb_json(item) for item in dynamo_json]
    else:
        return dynamo_json