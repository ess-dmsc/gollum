import time
import argparse
from gollum_listener import GollumListener
from gollum_writer import GollumWriter


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-mc", "--motive_client", required=True)
    parser.add_argument("-ms", "--motive_server", required=True)
    parser.add_argument("-ks", "--kafka_server", required=True)
    args = parser.parse_args()

    listener = GollumListener(args.motive_client, args.motive_server)
    writer = GollumWriter(args.kafka_server)

    frame_msg_queue = listener.frame_msg_queue
    rigid_body_msg_queue = listener.rigid_body_msg_queue

    listener.start_streaming()

    while True:
        frame_item = frame_msg_queue.get()
        rigid_body_item = rigid_body_msg_queue.get()

        stamp_data_received = frame_item["stamp_data_received"]

        rigid_body_item["timestamp"] = time.time_ns()  # stamp_data_received
        writer.produce("ymir_metrology", rigid_body_item) # gollum

        frame_msg_queue.task_done()
        rigid_body_msg_queue.task_done()


# python main.py -mc 127.0.0.1 -ms 127.0.0.1 -ks 10.100.1.19:9092