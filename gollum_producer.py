from confluent_kafka import Producer
from streaming_data_types import serialise_f144


class GollumProducer:
    def __init__(self, kafka_server):
        producer_config = {
            "bootstrap.servers": kafka_server,
            "message.max.bytes": "20000000",
        }
        self.producer = Producer(producer_config)

    def produce(self, topic, messages):
        for msg in messages:
            self.producer.produce(topic, msg)
        self.producer.flush()
