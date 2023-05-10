import argparse
import time

from gollum_client import DataListener, Inquirer, unpack_frame_data
from gollum_producer import (GollumProducer,
                             convert_rigid_bodies_to_flatbuffers,
                             convert_rigid_body_names_to_flatbuffers)

FRAME_DATA = "frame_data"
BODY_NAMES = "body_names"
COMMAND_PORT = 1510
DATA_PORT = 1511


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-mc", "--multicast_address", required=True)
    parser.add_argument("-la", "--local_address", required=True)
    parser.add_argument("-b", "--kafka_broker", required=True)
    parser.add_argument("-t", "--topic", required=True)
    args = parser.parse_args()

    producer = GollumProducer(args.kafka_broker)

    inquirer = Inquirer(args.local_address, COMMAND_PORT)
    data_listener = DataListener(args.multicast_address, args.local_address, DATA_PORT)
    rigid_bodies_map = {}
    last_update = time.monotonic()
    count = 0
    last_published = time.time()

    try:
        while True:
            try:
                if not rigid_bodies_map or time.monotonic() > last_update + 1.0:
                    rigid_bodies = inquirer.request_rigid_bodies()
                    rigid_bodies_map = {
                        body["id"]: body["name"].decode() for body in rigid_bodies
                    }
                    last_update = time.monotonic()
                    msgs = convert_rigid_body_names_to_flatbuffers(list(rigid_bodies_map.values()), time.time_ns())
                    producer.produce(args.topic, msgs)

                timestamp = time.time_ns()
                data = data_listener.fetch_data()

                if frame_data := unpack_frame_data(data):
                    msgs = convert_rigid_bodies_to_flatbuffers(
                        frame_data["rigid_bodies"], rigid_bodies_map, timestamp
                    )
                    producer.produce(args.topic, msgs)
                    now = time.time()
                    print(now - last_published)
                    last_published = now
            except Exception as error:
                print(f"Gollum issue: {error}")
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        data_listener.close()
        inquirer.close()
        producer.close()
