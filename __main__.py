from gollum_listener import GollumListener


listener = GollumListener("127.0.0.1", "127.0.0.1")

frame_msg_queue = listener.frame_msg_queue
rigid_body_msg_queue = listener.rigid_body_msg_queue

listener.start_streaming()
while True:
    frame_item = frame_msg_queue.get()
    rigid_body_item = rigid_body_msg_queue.get()

    print(frame_item)
    print(rigid_body_item)

    frame_msg_queue.task_done()
    rigid_body_msg_queue.task_done()