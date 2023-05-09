import argparse
import queue
import threading
import time

from gollum_client import DataListener, Inquirer, unpack_frame_data
from gollum_producer import (GollumProducer,
                             convert_rigid_bodies_to_flatbuffers,
                             convert_rigid_body_names_to_flatbuffers)

FRAME_DATA = "frame_data"
BODY_NAMES = "body_names"
COMMAND_PORT = 1510
DATA_PORT = 1511
NUM_TO_SKIP = 6


def process_updates(job_queue, broker, topic):
    producer = GollumProducer(broker)
    rigid_bodies_map = {}

    while True:
        data_type, data, timestamp = job_queue.get()
        if data_type == FRAME_DATA:
            if frame_data := unpack_frame_data(data):
                msgs = convert_rigid_bodies_to_flatbuffers(
                    frame_data["rigid_bodies"], rigid_bodies_map, timestamp
                )
                producer.produce(topic, msgs)
        elif data_type == BODY_NAMES:
            msgs = convert_rigid_body_names_to_flatbuffers(data, timestamp)
            producer.produce(topic, msgs)
        job_queue.task_done()
        print(job_queue.qsize())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-mc", "--multicast_address", required=True)
    parser.add_argument("-la", "--local_address", required=True)
    parser.add_argument("-b", "--kafka_broker", required=True)
    parser.add_argument("-t", "--topic", required=True)
    args = parser.parse_args()

    job_queue = queue.Queue()
    threading.Thread(
        target=process_updates, daemon=True, args=(job_queue, args.kafka_broker, args.topic)
    ).start()

    inquirer = Inquirer(args.local_address, COMMAND_PORT)
    data_listener = DataListener(args.multicast_address, args.local_address, DATA_PORT)
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
                    job_queue.put(
                        (BODY_NAMES, rigid_bodies_map, time.time_ns())
                    )

                timestamp = time.time_ns()
                data = data_listener.fetch_data()
                count += 1

                if data and count < NUM_TO_SKIP:
                    # Only send every nth update to avoid lag
                    continue

                count = 0
                job_queue.put((FRAME_DATA, data, timestamp))
            except Exception as error:
                print(f"Gollum issue: {error}")
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        data_listener.close()
        inquirer.close()

    job_queue.join()
