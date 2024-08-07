import json

from confluent_kafka import Producer
from scipy.spatial.transform import Rotation
from streaming_data_types import serialise_f144, serialise_json


def convert_rigid_body_to_flatbuffers(body, body_name, timestamp):
    messages = []
    for axis, value in zip(["x", "y", "z"], body["pos"]):
        name = f"{body_name}:{axis}"
        messages.append(serialise_f144(name, value, timestamp))
    euler = Rotation.from_quat(body["rot"]).as_euler("xyz", degrees=True)
    for axis, value in zip(["alpha", "beta", "gamma"], euler):
        name = f"{body_name}:{axis}"
        messages.append(serialise_f144(name, value, timestamp))
    for axis, value in zip(["qx", "qy", "qz", "qw"], body["rot"]):
        name = f"{body_name}:{axis}"
        messages.append(serialise_f144(name, value, timestamp))
    messages.append(
        serialise_f144(f"{body_name}:valid", 1 if body["valid"] else 0, timestamp)
    )
    return messages


def convert_rigid_body_names_to_flatbuffers(names, timestamp):
    data = {"timestamp": timestamp, "names": names}
    return [serialise_json(json.dumps(data))]


class GollumProducer:
    def __init__(self, kafka_server, security_config):
        producer_config = {
            "bootstrap.servers": kafka_server,
            "message.max.bytes": "20000000",
        }
        producer_config.update(security_config)
        self.producer = Producer(producer_config)

    def produce(self, topic, messages):
        for msg in messages:
            self.producer.produce(topic, msg)
        # A quick flush!
        print("flush", self.producer.flush(timeout=0))

    def close(self):
        self.producer.flush()
