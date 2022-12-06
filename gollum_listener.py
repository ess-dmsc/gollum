from OptiTrack.NatNetClient import NatNetClient


class GollumListener:
    def __init__(self, client_address, server_address, use_multicast=True):
        self.streaming_client = NatNetClient()
        self.streaming_client.set_client_address(client_address)
        self.streaming_client.set_server_address(server_address)
        self.streaming_client.set_use_multicast(use_multicast)
        self.streaming_client.new_frame_listener = self.new_frame_callback
        self.streaming_client.rigid_body_listener = self.rigid_body_frame_callback

    def new_frame_callback(self, data_dict):
        print("Hello", data_dict)

    def rigid_body_frame_callback(self, new_id, position, rotation):
        print("weqweweqwewqqweqweqw", new_id, position, rotation)

    def start_streaming(self):
        if not self.streaming_client.run():
            raise RuntimeError("Could not start streaming client.")
