import time

from gollum_listener import GollumListener
from gollum_writer import GollumWriter


listener = GollumListener("127.0.0.1", "127.0.0.1")
writer = GollumWriter("[::1]:9092")

frame_msg_queue = listener.frame_msg_queue
rigid_body_msg_queue = listener.rigid_body_msg_queue

listener.start_streaming()
while True:
    frame_item = frame_msg_queue.get()
    rigid_body_item = rigid_body_msg_queue.get()

    stamp_data_received = frame_item["stamp_data_received"]
    print(frame_item)
    rigid_body_item["timestamp"] = time.time_ns() # stamp_data_received
    writer.produce("gollum", rigid_body_item)

    frame_msg_queue.task_done()
    rigid_body_msg_queue.task_done()