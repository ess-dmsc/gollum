from confluent_kafka import Producer
import json


class GollumWriter:
    def __init__(self, server_address):
        producer_config = {
                "bootstrap.servers": server_address,
                "message.max.bytes": "20000000",
            }
        self.producer = Producer(producer_config)

    def produce(self, topic, message):
        message = json.dumps(message)
        self.producer.produce(topic, message.encode())
        self.producer.flush()
