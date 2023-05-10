import json

from confluent_kafka import Producer
from scipy.spatial.transform import Rotation
from streaming_data_types import serialise_f144, serialise_json


def convert_rigid_bodies_to_flatbuffers(rigid_bodies, id_map, timestamp):
    messages = []
    for body in rigid_bodies:
        body_name = id_map[body["id"]]

        #  TODO: Are the axis in the right direction for nexus?
        for axis, value in zip(["x", "y", "z"], body["pos"]):
            name = f"{body_name}:pos:{axis}"
            messages.append(serialise_f144(name, value, timestamp))

        #  TODO: Check the values are correct.
        #  TODO: Does nexus want deg or rad?
        #  TODO: Are the axis in the right direction for nexus?
        #  TODO: can motive give us euler instead of quats? It can when dumping to csv...
        euler = Rotation.from_quat(body["rot"]).as_euler("xyz", degrees=True)
        for axis, value in zip(["x", "y", "z"], euler):
            name = f"{body_name}:rot:{axis}"
            messages.append(serialise_f144(name, value, timestamp))

        messages.append(
            serialise_f144(f"{body_name}:valid", 1 if body["valid"] else 0, timestamp)
        )

    return messages


def convert_rigid_body_names_to_flatbuffers(names, timestamp):
    data = {"timestamp": timestamp, "names": names}
    return [serialise_json(json.dumps(data))]


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
        # A quick flush!
        print("flush", self.producer.flush(timeout=0))

    def close(self):
        self.producer.flush()
