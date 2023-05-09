import argparse
import time

from scipy.spatial.transform import Rotation
from streaming_data_types import serialise_f144

from gollum_client import DataListener, Inquirer, unpack_frame_data
from gollum_writer import GollumWriter


def generate_flatbuffer_messages(rigid_bodies, id_map, timestamp):
    messages = []
    for body in rigid_bodies:
        body_name = id_map[body["id"]]

        #  TODO: Are the axis in the right direction for nexus?
        for axis, value in zip(["x", "y", "z"], body["pos"]):
            name = f"{body_name}:{axis}:pos"
            messages.append(serialise_f144(name, value, timestamp))

        #  TODO: Check the values are correct.
        #  TODO: Does nexus want deg or rad?
        #  TODO: Are the axis in the right direction for nexus?
        #  TODO: can motive give us euler instead of quats? It can when dumping to csv...
        euler = Rotation.from_quat(body["rot"]).as_euler("xyz", degrees=True)
        for axis, value in zip(["x", "y", "z"], euler):
            name = f"{body_name}:{axis}:rot"
            messages.append(serialise_f144(name, value, timestamp))

        messages.append(
            serialise_f144(f"{body_name}:valid", 1 if body["valid"] else 0, timestamp)
        )

    return messages


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-mc", "--multicast_address", required=True)
    parser.add_argument("-la", "--local_address", required=True)
    parser.add_argument("-ks", "--kafka_server", required=True)
    args = parser.parse_args()

    inquirer = Inquirer(args.local_address, 1510)
    data_listener = DataListener(args.multicast_address, args.local_address, 1511)
    rigid_bodies_map = {}
    last_update = time.monotonic()

    try:
        while True:
            if not rigid_bodies_map or time.monotonic() > last_update + 1.0:
                rigid_bodies = inquirer.request_rigid_bodies()
                rigid_bodies_map = {
                    body["id"]: body["name"].decode() for body in rigid_bodies
                }
                last_update = time.monotonic()

            data = data_listener.fetch_data()
            timestamp = time.time_ns()

            if frame_data := unpack_frame_data(data):
                msgs = generate_flatbuffer_messages(
                    frame_data["rigid_bodies"], rigid_bodies_map, timestamp
                )

            time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        data_listener.close()
        inquirer.close()

    # listener = GollumListener(args.motive_client, args.motive_server)
    # writer = GollumWriter(args.kafka_server)
    #
    # frame_msg_queue = listener.frame_msg_queue
    # rigid_body_msg_queue = listener.rigid_body_msg_queue
    #
    # listener.start_streaming()
    #
    # while True:
    #     frame_item = frame_msg_queue.get()
    #     rigid_body_item = rigid_body_msg_queue.get()
    #
    #     stamp_data_received = frame_item["stamp_data_received"]
    #
    #     rigid_body_item["timestamp"] = time.time_ns()  # stamp_data_received
    #     writer.produce("ymir_metrology", rigid_body_item) # gollum
    #
    #     frame_msg_queue.task_done()
    #     rigid_body_msg_queue.task_done()


# python main.py -mc 127.0.0.1 -ms 127.0.0.1 -ks 10.100.1.19:9092
