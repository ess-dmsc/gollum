# from OptiTrack.NatNetClient import NatNetClient
from MyNatNetClient import NatNetClient
import queue


class GollumListener:
    def __init__(self, motive_client, motive_server, use_multicast=True):
        self.streaming_client = NatNetClient()
        self.streaming_client.set_client_address(motive_client)
        self.streaming_client.set_server_address(motive_server)
        # self.streaming_client.set_use_multicast(use_multicast)
        self.streaming_client.new_frame_listener = self.new_frame_callback
        self.streaming_client.rigid_body_listener = self.rigid_body_frame_callback
        self.frame_msg_queue = queue.Queue()
        self.rigid_body_msg_queue = queue.Queue()

    def new_frame_callback(self, data_dict):
        # print(data_dict)
        self.frame_msg_queue.put(data_dict)

    def rigid_body_frame_callback(self, new_id, position, rotation, is_valid):
        rigid_body_info = {"new_id": new_id, "position": position, "rotation": rotation}
        self.rigid_body_msg_queue.put(rigid_body_info)

    def start_streaming(self):
        if not self.streaming_client.run():
            raise RuntimeError("Could not start streaming client.")

    def request_model_definitions(self):
        self.streaming_client.request_model_definitions()
