import argparse
import time

from gollum_client import DataListener, Inquirer, unpack_frame_data
from gollum_producer import GollumProducer, convert_rigid_bodies_to_flatbuffers


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
                    msgs = convert_rigid_bodies_to_flatbuffers(
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
