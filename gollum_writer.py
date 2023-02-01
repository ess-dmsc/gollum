from confluent_kafka import Producer
from streaming_data_types import serialise_f144


class GollumWriter:
    def __init__(self, kafka_server):
        producer_config = {
            "bootstrap.servers": kafka_server,
            "message.max.bytes": "20000000",
        }
        self.producer = Producer(producer_config)

    def produce(self, topic, message):
        timestamp = message["timestamp"]
        rotation = message["rotation"]
        prefix = f"rigid_body_{message['new_id']}"
        positions_order = ["x", "y", "z"]
        # rotations_order = ["alpha", "beta", "gama"]

        for name, value in zip(positions_order, message["position"]):
            pos_source_name = f"{prefix}_pos_{name}"
            self.producer.produce(topic, serialise_f144(pos_source_name, value, timestamp))

        # for name, value in zip(rotations_order, message["rotation"]):
        #     rot_source_name = f"{prefix}_rot_{name}"
        #     self.producer.produce(topic, serialise_f144(rot_source_name, value, timestamp))

        rot_source_name = f"{prefix}_rotation"
        self.producer.produce(topic, serialise_f144(rot_source_name, rotation, timestamp))

        self.producer.flush()
