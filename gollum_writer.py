from confluent_kafka import Producer
from streaming_data_types import serialise_f144
import numpy as np


class GollumWriter:
    def __init__(self, server_address):
        producer_config = {
                "bootstrap.servers": server_address,
                "message.max.bytes": "20000000",
            }
        self.producer = Producer(producer_config)

    def produce(self, topic, message):
        timestamp = message["timestamp"]
        prefix = f"rigid_body_{message['new_id']}"
        positions_order = ['x', 'y', 'z']

        for name, value in zip(positions_order, message["position"]):
            source_name = f"{prefix}_pos_{name}"
            self.producer.produce(topic, serialise_f144(source_name, value, timestamp))
        self.producer.flush()

