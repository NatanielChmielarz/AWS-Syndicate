from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda

_LOG = get_logger(__name__)

import boto3
import uuid
import json
import os
from datetime import datetime


class UuidGenerator(AbstractLambda):

    def validate_request(self, event) -> dict:
        pass
        
    def handle_request(self, event, context):
        BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'uuid-storage')
        s3_client = boto3.client('s3')

        try:
            uuids = [str(uuid.uuid4()) for _ in range(10)]

            payload = json.dumps({
                'ids': uuids
            },indent=4)

            timestamp = datetime.now().isoformat(timespec='milliseconds') + "Z"
            filename = f"{timestamp}"

            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=f"{timestamp}",
                Body=payload,
                ContentType='application/json'
            )

            _LOG.info(f'Successfully uploaded UUIDs to S3: s3://{BUCKET_NAME}/{filename}')

        except Exception as error:
            _LOG.error(f'Error: {error}')
            raise error
        

HANDLER = UuidGenerator()


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)
