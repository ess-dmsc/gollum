import argparse
import time

from scipy.spatial.transform import Rotation
from streaming_data_types import serialise_f144

from gollum_client import DataListener, Inquirer, unpack_frame_data
from gollum_producer import GollumProducer


def generate_flatbuffer_messages(rigid_bodies, id_map, timestamp):
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-mc", "--multicast_address", required=True)
    parser.add_argument("-la", "--local_address", required=True)
    parser.add_argument("-b", "--kafka_broker", required=True)
    parser.add_argument("-t", "--topic", required=True)
    args = parser.parse_args()

    producer = GollumProducer(args.kafka_broker)
    inquirer = Inquirer(args.local_address, 1510)
    data_listener = DataListener(args.multicast_address, args.local_address, 1511)
    rigid_bodies_map = {}
    last_update = time.monotonic()
    count = 0

    try:
        while True:
            try:
                if not rigid_bodies_map or time.monotonic() > last_update + 1.0:
                    rigid_bodies = inquirer.request_rigid_bodies()
                    rigid_bodies_map = {
                        body["id"]: body["name"].decode() for body in rigid_bodies
                    }
                    last_update = time.monotonic()

                data = data_listener.fetch_data()
                timestamp = time.time_ns()
                count += 1

                if data and count < 5:
                    # Only send every 5th update to avoid lag
                    continue

                count = 0

                if frame_data := unpack_frame_data(data):
                    msgs = generate_flatbuffer_messages(
                        frame_data["rigid_bodies"], rigid_bodies_map, timestamp
                    )
                    producer.produce(args.topic, msgs)
            except Exception as error:
                print(f"Gollum issue: {error}")
            time.sleep(0.0001)
    except KeyboardInterrupt:
        pass
    finally:
        data_listener.close()
        inquirer.close()
