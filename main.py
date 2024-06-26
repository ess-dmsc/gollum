import configargparse as argparse
import time

from collections import defaultdict
from gollum_client import DataListener, Inquirer, unpack_frame_data
from gollum_producer import (GollumProducer,
                             convert_rigid_body_names_to_flatbuffers, convert_rigid_body_to_flatbuffers)
from kafka_security import get_kafka_security_config

FRAME_DATA = "frame_data"
BODY_NAMES = "body_names"
COMMAND_PORT = 1510
DATA_PORT = 1511
PUBLISH_MS = 500


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-mc", "--multicast_address", required=True)
    parser.add_argument("-la", "--local_address", required=True)
    parser.add_argument("-b", "--kafka_broker", required=True)
    parser.add_argument("-t", "--topic", required=True)

    kafka_sec_args = parser.add_argument_group("Kafka security arguments")
    kafka_sec_args.add_argument(
        "-kc",
        "--kafka-config-file",
        is_config_file=True,
        help="Kafka security configuration file",
    )
    kafka_sec_args.add_argument(
        "--security-protocol",
        type=str,
        help="Kafka security protocol",
    )
    kafka_sec_args.add_argument(
        "--sasl-mechanism",
        type=str,
        help="Kafka SASL mechanism",
    )
    kafka_sec_args.add_argument(
        "--sasl-username",
        type=str,
        help="Kafka SASL username",
    )
    kafka_sec_args.add_argument(
        "--sasl-password",
        type=str,
        help="Kafka SASL password",
    )
    kafka_sec_args.add_argument(
        "--ssl-cafile",
        type=str,
        help="Kafka SSL CA certificate path",
    )

    args = parser.parse_args()

    kafka_security_config = get_kafka_security_config(
        args.security_protocol,
        args.sasl_mechanism,
        args.sasl_username,
        args.sasl_password,
        args.ssl_cafile,
    )

    producer = GollumProducer(args.kafka_broker, kafka_security_config)

    inquirer = Inquirer(args.local_address, COMMAND_PORT)
    data_listener = DataListener(args.multicast_address, args.local_address, DATA_PORT)
    rigid_bodies_map = {}
    last_rigid_body_update = time.monotonic()
    last_published_ns = defaultdict(int)

    try:
        while True:
            try:
                if not rigid_bodies_map or time.monotonic() > last_rigid_body_update + 1.0:
                    # Check to see if rigid bodies definitions have changed
                    rigid_bodies = inquirer.request_rigid_bodies()
                    rigid_bodies_map = {
                        body["id"]: body["name"].decode() for body in rigid_bodies
                    }
                    last_rigid_body_update = time.monotonic()
                    msgs = convert_rigid_body_names_to_flatbuffers(list(rigid_bodies_map.values()), time.time_ns())
                    producer.produce(args.topic, msgs)

                timestamp_ns = time.time_ns()
                data = data_listener.fetch_data()

                if frame_data := unpack_frame_data(data):
                    bodies = frame_data["rigid_bodies"]
                    for body in bodies:
                        body_id = body["id"]
                        if last_published_ns[body_id] + PUBLISH_MS * 1000000 < timestamp_ns:
                            msgs = convert_rigid_body_to_flatbuffers(body, rigid_bodies_map[body_id], timestamp_ns)
                            producer.produce(args.topic, msgs)
                            last_published_ns[body_id] = timestamp_ns
            except Exception as error:
                print(f"Gollum issue: {error}")
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        data_listener.close()
        inquirer.close()
        producer.close()
