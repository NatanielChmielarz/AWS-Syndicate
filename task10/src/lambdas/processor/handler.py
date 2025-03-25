from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda
import json
import os
import uuid
import boto3
from decimal import Decimal

_LOG = get_logger(__name__)
import requests

dynamodb = boto3.resource("dynamodb")


class WeatherHandler:

    def __init__(self):
        self.weather_api_url = "https://api.open-meteo.com/v1/forecast"
        self.default_params = {
            "latitude": 52.52,
            "longitude": 13.41,
            "current": "temperature_2m,wind_speed_10m",
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        }
        self.table_name = os.environ.get("TARGET_TABLE")

    def fetch_weather_data(self):
        """Fetches weather data from Open-Meteo API."""
        response = requests.get(self.weather_api_url, params=self.default_params)
        response.raise_for_status()
        return response.json()

    def process_weather_data(self, weather):
        """Processes weather data into the required structure."""
        return {
            "elevation": weather["elevation"],
            "generationtime_ms": weather["generationtime_ms"],
            "hourly": {
                "temperature_2m": weather["hourly"]["temperature_2m"],
                "time": weather["hourly"]["time"],
            },
            "hourly_units": {
                "temperature_2m": weather["hourly_units"]["temperature_2m"],
                "time": weather["hourly_units"]["time"],
            },
            "latitude": weather["latitude"],
            "longitude": weather["longitude"],
            "timezone": weather["timezone"],
            "timezone_abbreviation": weather["timezone_abbreviation"],
            "utc_offset_seconds": weather["utc_offset_seconds"],
        }

    def save_to_dynamodb(self, record):
        """Stores the record in the DynamoDB table."""
        table = dynamodb.Table(self.table_name)
        item = json.loads(
            json.dumps(record), parse_float=Decimal
        )  # Convert floats to Decimal
        table.put_item(Item=item)


class Processor(AbstractLambda):

    def validate_request(self, event) -> dict:
        pass

    def handle_request(self, event, context):
        """Handles incoming API requests."""
        _LOG.info(event)

        if "rawPath" in event and event["rawPath"] in ["/weather", "/"]:
            try:
                weather_handler = WeatherHandler()
                weather_data = weather_handler.fetch_weather_data()
                forecast = weather_handler.process_weather_data(weather_data)

                record = {"id": str(uuid.uuid4()), "forecast": forecast}

                _LOG.info(record)
                _LOG.info(forecast)

                weather_handler.save_to_dynamodb(record)

                return {
                    "headers": {"Content-Type": "application/json"},
                    "statusCode": 200,
                    "body": json.dumps(weather_data),
                }
            except Exception as e:
                _LOG.error(f"Error processing request: {e}")
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": "Internal Server Error"}),
                }

        return {"statusCode": 400, "body": json.dumps({"error": "Invalid request"})}


HANDLER = Processor()


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)
