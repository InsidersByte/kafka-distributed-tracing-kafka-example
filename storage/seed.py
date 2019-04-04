import logging
from uuid import uuid4
import json

from redis import Redis
from faker import Faker

fake = Faker()


def make_fake_message():
    return {"id": fake.uuid4(), "message": fake.text()}

if __name__ == "__main__":
    logging.basicConfig()
    redis_client = Redis()

    print("saving fake messages...")
    fake_messages = [make_fake_message() for i in range(1, 10000)]
    redis_client.set("messages", json.dumps(fake_messages))
    print("finished saving fake messages")
