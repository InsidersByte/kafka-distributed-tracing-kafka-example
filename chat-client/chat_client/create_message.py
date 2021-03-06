import time
import argparse
from pprint import pprint

import grpc
from jaeger_client import Config
from grpc_opentracing import open_tracing_client_interceptor, ActiveSpanSource
from grpc_opentracing.grpcext import intercept_channel
from google.protobuf.json_format import MessageToDict
from faker import Faker

import chat_pb2_grpc
import chat_pb2

fake = Faker()


class FixedActiveSpanSource(ActiveSpanSource):
    def __init__(self):
        self.active_span = None

    def get_active_span(self):
        return self.active_span


def create_message(tracer, active_span_source, stub):
    with tracer.start_span("create message") as span:
        active_span_source.active_span = span
        response = stub.CreateMessage(chat_pb2.CreateMessageRequest(message=fake.text()))
        return response


def run():
    config = Config(
        config={"sampler": {"type": "const", "param": 1}, "logging": True},
        service_name="chat-client",
    )
    tracer = config.initialize_tracer()
    active_span_source = FixedActiveSpanSource()
    tracer_interceptor = open_tracing_client_interceptor(
        tracer, active_span_source=active_span_source, log_payloads=True
    )

    channel = grpc.insecure_channel("localhost:50051")
    channel = intercept_channel(channel, tracer_interceptor)
    stub = chat_pb2_grpc.ChatStub(channel)

    response = create_message(tracer, active_span_source, stub)
    pprint(MessageToDict(response))

    time.sleep(2)
    tracer.close()
    time.sleep(2)


if __name__ == "__main__":
    run()
