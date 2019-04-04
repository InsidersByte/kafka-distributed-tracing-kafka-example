from concurrent import futures
import time
import logging
from datetime import datetime
import json
from uuid import uuid4

import grpc
from jaeger_client import Config
from grpc_opentracing import open_tracing_server_interceptor
from grpc_opentracing.grpcext import intercept_server
from redis import Redis
import redis_opentracing
from kafka import KafkaProducer
import opentracing

import chat_pb2_grpc
import chat_pb2

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


class ChatServicer(chat_pb2_grpc.ChatServicer):
    def __init__(self, tracer, redis_client, kafka_producer):
        self._tracer = tracer
        self._redis_client = redis_client
        self._kafka_producer = kafka_producer

    def ListMessages(self, request, context):
        with self._tracer.start_span(
            "ListMessages", child_of=context.get_active_span().context
        ) as scope:
            # redis doesn't automatically assign the child context (https://github.com/opentracing-contrib/python-redis/issues/10)
            with self._tracer.start_span("Fetching Messages", child_of=scope):
                messages = self._redis_client.get("messages")

            with self._tracer.start_span("Parsing Messages", child_of=scope):
                messages = json.loads(messages)

            with self._tracer.start_span("Serializing Messages", child_of=scope):
                messages = list(
                    map(
                        lambda message: chat_pb2.Message(
                            id=message["id"], message=message["message"]
                        ),
                        messages,
                    )
                )

            with self._tracer.start_span("Serializing Response", child_of=scope):
                response = chat_pb2.ListMessagesResponse(messages=messages)

            return response

    def CreateMessage(self, request, context):
        with self._tracer.start_span(
            "CreateMessage", child_of=context.get_active_span().context
        ) as scope:
            id = uuid4()
            message = request.message

            with self._tracer.start_span(
                "Publishing Message", child_of=scope
            ) as publishing_scope:
                headers = {}
                self._tracer.inject(
                    publishing_scope.context, opentracing.Format.TEXT_MAP, headers
                )
                headers = [(key, value.encode('utf-8')) for key, value in headers.items()]

                self._kafka_producer.send(
                    "message-created",
                    {"id": str(id), "message": message},
                    headers=headers
                )

            with self._tracer.start_span("Serializing Response", child_of=scope):
                return chat_pb2.Message(id=str(id), message=message)


def serve():
    config = Config(
        config={"sampler": {"type": "const", "param": 1}, "logging": True},
        service_name="chat-server",
    )
    tracer = config.initialize_tracer()
    tracer_interceptor = open_tracing_server_interceptor(tracer, log_payloads=True)

    redis_opentracing.init_tracing(tracer_interceptor)
    redis_client = Redis()

    kafka_producer = KafkaProducer(
        bootstrap_servers="127.0.0.1:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    server = intercept_server(server, tracer_interceptor)
    chat_pb2_grpc.add_ChatServicer_to_server(
        ChatServicer(tracer, redis_client, kafka_producer), server
    )
    server.add_insecure_port("[::]:50051")
    server.start()

    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    logging.basicConfig()
    serve()
