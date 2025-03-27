from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda
import boto3
import json
import uuid
import os
import random
from decimal import Decimal
import datetime

_LOG = get_logger("ApiHandler-handler")


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class ApiHandler(AbstractLambda):
    def __init__(self):
        self.cognito = boto3.client("cognito-idp")
        self.dynamodb = boto3.resource("dynamodb")
        self.user_pool_id = os.getenv("cup_id")
        self.client_id = os.getenv("cup_client_id")
        self.tables_table = self._get_table("tables", "test1")
        self.reservations_table = self._get_table("reservations", "test2")

    def _get_table(self, env_var, default):
        return self.dynamodb.Table(os.environ.get(env_var, default))

    def _json_response(self, status_code, body):
        return {
            "statusCode": status_code,
            "body": json.dumps(body, cls=DecimalEncoder),
            "isBase64Encoded": False,
        }

    def signup(self, event):
        body = json.loads(event["body"])
        try:
            response = self.cognito.sign_up(
                ClientId=self.client_id,
                Username=body["email"],
                Password=body["password"],
                UserAttributes=[
                    {"Name": "email", "Value": body["email"]},
                    {"Name": "given_name", "Value": body["firstName"]},
                    {"Name": "family_name", "Value": body["lastName"]},
                ],
            )
            _LOG.info(f"Sign-up response: {response}")

            if not response.get("UserConfirmed"):
                confirm_resp = self.cognito.admin_confirm_sign_up(
                    UserPoolId=self.user_pool_id, Username=body["email"]
                )
                _LOG.info(f"Confirm response: {confirm_resp}")
                response["UserConfirmed"] = True

            return self._json_response(
                200, {"message": "Sign-up successful", "body": response}
            )
        except Exception as e:
            return self._json_response(400, {"message": "Bad request", "error": str(e)})

    def signin(self, event):
        body = json.loads(event["body"])
        auth_params = {"USERNAME": body["email"], "PASSWORD": body["password"]}

        try:
            response = self.cognito.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                AuthFlow="ADMIN_NO_SRP_AUTH",
                AuthParameters=auth_params,
            )
            _LOG.info(f"Authentication response: {response}")

            if response:
                return self._json_response(
                    200, {"idToken": response["AuthenticationResult"]["IdToken"]}
                )
            else:
                return self._json_response(200, {"idToken": None})
        except Exception as e:
            _LOG.error(f"Error in signin: {e}")
            return self._json_response(400, {"message": "Bad request", "error": str(e)})

    def get_tables(self, event):
        try:
            response = self.tables_table.scan()
            items = response["Items"]
            return self._json_response(
                200, {"tables": sorted(items, key=lambda item: item["id"])}
            )
        except Exception as e:
            return self._json_response(400, {"message": "Bad request", "error": str(e)})

    def create_table(self, event):
        body = json.loads(event["body"])
        try:
            item = {
                "id": int(body["id"]),
                "number": body["number"],
                "places": body["places"],
                "isVip": body["isVip"],
                "minOrder": body["minOrder"],
            }
            item = json.loads(json.dumps(item))
            self.tables_table.put_item(Item=item)
            return self._json_response(200, {"id": body["id"]})
        except Exception as e:
            return self._json_response(400, {"message": "Bad request", "error": str(e)})

    def get_table_by_id(self, table_id):
        try:
            response = self.tables_table.get_item(Key={"id": int(table_id)})
            if "Item" in response:
                return self._json_response(200, {"body": response["Item"]})
            return self._json_response(404, {"message": "Table not found"})
        except Exception as e:
            return self._json_response(400, {"message": "Bad request", "error": str(e)})

    def create_reservation(self, event):
        try:
            body = json.loads(event["body"])
            _LOG.info(f"Received reservation request: {body}")
            required_fields = ["tableNumber", "date", "slotTimeStart", "slotTimeEnd"]
            if not all(field in body for field in required_fields):
                return self._json_response(400, {"message": "Missing required fields"})

            table_number = body["tableNumber"]
            date = body["date"]
            slot_start = body["slotTimeStart"]
            slot_end = body["slotTimeEnd"]

            tables_response = self.tables_table.scan()
            table_numbers = [table["number"] for table in tables_response["Items"]]

            if table_number not in table_numbers:
                return self._json_response(400, {"message": "Table does not exist"})

            proposed_start = datetime.strptime(slot_start, "%H:%M").time()
            proposed_end = datetime.strptime(slot_end, "%H:%M").time()

            reservations_response = self.reservations_table.scan(
                FilterExpression="#tn = :table_number AND #d = :date",
                ExpressionAttributeNames={"#tn": "tableNumber", "#d": "date"},
                ExpressionAttributeValues={
                    ":table_number": table_number,
                    ":date": date,
                },
            )

            for res in reservations_response.get("Items", []):
                existing_start = datetime.strptime(res["slotTimeStart"], "%H:%M").time()
                existing_end = datetime.strptime(res["slotTimeEnd"], "%H:%M").time()

                if proposed_start < existing_end and proposed_end > existing_start:
                    return self._json_response(
                        400, {"message": "Time conflict: Table is already reserved."}
                    )

            reservation_id = str(uuid.uuid4())
            self.reservations_table.put_item(Item={"id": reservation_id, **body})

            _LOG.info(f"Reservation created successfully: {reservation_id}")

            return self._json_response(200, {"reservationId": reservation_id})

        except Exception as e:
            _LOG.error(f"Error while creating reservation: {str(e)}")
            return self._json_response(400, {"message": "Bad request", "error": str(e)})

    def get_reservations(self, event):
        try:
            response = self.reservations_table.scan()
            items = response["Items"]
            for i in items:
                del i["id"]
            items = sorted(items, key=lambda item: item["tableNumber"])
            return self._json_response(200, {"reservations": response["Items"]})
        except Exception as e:
            return self._json_response(400, {"message": "Bad request", "error": str(e)})

    def handle_request(self, event, context):
        routes = {
            ("POST", "/signup"): self.signup,
            ("POST", "/signin"): self.signin,
            ("GET", "/tables"): self.get_tables,
            ("GET", "/tables/{tableId}"): self.get_table_by_id,
            ("POST", "/tables"): self.create_table,
            ("POST", "/reservations"): self.create_reservation,
            ("GET", "/reservations"): self.get_reservations,
        }
        route_key = (event["httpMethod"], event.get("resource"))
        if route_key == ("GET", "/tables/{tableId}"):
            table_id = event.get("pathParameters", {}).get("tableId")
            if not table_id:
                return self._json_response(400, {"message": "Missing tableId"})
            return self.get_table_by_id(event, table_id)
        handler = routes.get(
            route_key, lambda _: self._json_response(400, {"message": "Invalid route"})
        )
        return handler(event)


HANDLER = ApiHandler()


def lambda_handler(event, context):
    return HANDLER.handle_request(event, context)
