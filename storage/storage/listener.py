import time
import logging
import json
from pprint import pprint

from jaeger_client import Config
from redis import Redis
import redis_opentracing
from kafka import KafkaConsumer
import opentracing

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


def listen():
    config = Config(
        config={"sampler": {"type": "const", "param": 1}, "logging": True},
        service_name="storage",
    )
    tracer = config.initialize_tracer()

    redis_opentracing.init_tracing(tracer)
    redis_client = Redis()

    kafka_consumer = KafkaConsumer(
        "message-created",
        bootstrap_servers="127.0.0.1:9092",
        value_deserializer=lambda v: json.loads(v, encoding="utf-8"),
    )

    for message in kafka_consumer:
        headers = dict((key, value.decode('utf-8')) for key, value in message.headers)
        span_context = tracer.extract(opentracing.Format.TEXT_MAP, headers)

        with tracer.start_span("Storing Message", child_of=span_context) as scope:
            with tracer.start_span("Fetching Messages", child_of=scope):
                messages = redis_client.get("messages")

            if not messages:
                messages = "[]"

            with tracer.start_span("Parsing Messages", child_of=scope):
                messages = json.loads(messages)

            messages.append(message.value)

            with tracer.start_span("Serializing Messages", child_of=scope):
                messages = json.dumps(messages)

            with tracer.start_span("Saving Messages", child_of=scope):
                redis_client.set("messages", messages)


if __name__ == "__main__":
    logging.basicConfig()
    listen()
