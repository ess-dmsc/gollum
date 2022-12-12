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
        source_name = None
        value = None
        for i in range(message["position"][0], message["position"][2]):
            if i == 0:
                source_name = "rigid_body_" + str(message['new_id']) + "_pos_x"
                value = message["position"][0]
            elif i == 1:
                source_name = "rigid_body_" + str(message['new_id']) + "_pos_y"
                value = message["position"][1]
            else:
                source_name = "rigid_body_" + str(message['new_id']) + "_pos_z"
                value = message["position"][2]
        timestamp = message["timestamp"]
        message = serialise_f144(source_name, value, timestamp)
        self.producer.produce(topic, message)
        self.producer.flush()

