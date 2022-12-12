from confluent_kafka import Consumer
import uuid


consumer_config = {
    "bootstrap.servers": "[::1]:9092",
    "group.id": uuid.uuid4(),
    "default.topic.config": {"auto.offset.reset": "latest"},
}
consumer = Consumer(consumer_config)
consumer.subscribe(["gollum"])

while True:
    msg = consumer.poll(timeout=0.5)
    if msg is None:
        continue
    elif msg.value():
        print(msg.value())
