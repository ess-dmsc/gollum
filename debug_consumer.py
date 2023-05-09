import uuid

from confluent_kafka import Consumer
from streaming_data_types import deserialise_f144, deserialise_json

consumer_config = {
    "bootstrap.servers": "10.100.1.19:9092",
    "group.id": uuid.uuid4(),
    "default.topic.config": {"auto.offset.reset": "latest"},
}
consumer = Consumer(consumer_config)
consumer.subscribe(["ymir_metrology"])

while True:
    msg = consumer.poll(timeout=0.5)
    if msg is None:
        continue
    elif msg.value():
        try:
            print(deserialise_f144(msg.value()))
        except:
            print("\nNAMES", deserialise_json(msg.value()), "\n")
