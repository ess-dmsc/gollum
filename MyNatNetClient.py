import socket
import struct
from threading import Thread
import copy
import time
from OptiTrack import DataDescriptions
from OptiTrack import MoCapData
from Unpacker import Unpacker


PRINT_LEVEL = 0

# Client/server message ids
NAT_CONNECT = 0
NAT_SERVERINFO = 1
NAT_REQUEST = 2
NAT_RESPONSE = 3
NAT_REQUEST_MODELDEF = 4
NAT_MODELDEF = 5
NAT_REQUEST_FRAMEOFDATA = 6
NAT_FRAMEOFDATA = 7
NAT_MESSAGESTRING = 8
NAT_DISCONNECT = 9
NAT_KEEPALIVE = 10
NAT_UNRECOGNIZED_REQUEST = 100
NAT_UNDEFINED = 999999.9999

# Create structs for reading various object types to speed up parsing.
Vector2 = struct.Struct("<ff")
Vector3 = struct.Struct("<fff")
Quaternion = struct.Struct("<ffff")
FloatValue = struct.Struct("<f")
DoubleValue = struct.Struct("<d")
NNIntValue = struct.Struct("<I")
FPCalMatrixRow = struct.Struct("<ffffffffffff")
FPCorners = struct.Struct("<ffffffffffff")


class NatNetClient:
    def __init__(self):
        # Change this value to the IP address of the NatNet server.
        self.server_ip_address = "127.0.0.1"

        # Change this value to the IP address of your local network interface
        self.local_ip_address = "127.0.0.1"

        # This should match the multicast address listed in Motive's streaming settings.
        self.multicast_address = "239.255.42.99"

        # NatNet Command channel
        self.command_port = 1510

        # NatNet Data channel
        self.data_port = 1511

        self.use_multicast = True

        # NatNet stream version serveris capable of. This will be updated during initialization only.
        self.__nat_net_stream_version_server = [0, 0, 0, 0]

        # NatNet stream version. This will be updated to the actual version the server is using during runtime.
        self.__nat_net_requested_version = [0, 0, 0, 0]

        # server stream version. This will be updated to the actual version the server is using during initialization.
        self.__server_version = [0, 0, 0, 0]

        # Set this to a callback method of your choice to receive per-rigid-body data at each frame.
        self.rigid_body_listener = None
        self.new_frame_listener = None

        # Lock values once run is called
        self.__is_locked = False

        self.command_thread = None
        self.data_thread = None
        self.command_socket = None
        self.data_socket = None

        self.stop_threads = False

    def set_client_address(self, local_ip_address):
        pass
        # if not self.__is_locked:
        # self.local_ip_address = local_ip_address

    def set_server_address(self, server_ip_address):
        pass
        # if not self.__is_locked:
        # self.server_ip_address = server_ip_address

    def __create_command_socket(self):
        result = None
        if self.use_multicast:
            # Multicast case
            result = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
            # allow multiple clients on same machine to use multicast group address/port
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                result.bind(("", 0))
            except socket.error as msg:
                print("ERROR: command socket error occurred:\n%s" % msg)
                print(
                    "Check Motive/Server mode requested mode agreement.  You requested Multicast "
                )
                result = None

            # set to broadcast mode
            result.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # set timeout to allow for keep alive messages
            result.settimeout(2.0)
        else:
            # Unicast case
            result = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
            )
            try:
                result.bind((self.local_ip_address, 0))
            except socket.error as msg:
                print("ERROR: command socket error occurred:\n%s" % msg)
                print(
                    "Check Motive/Server mode requested mode agreement.  You requested Unicast "
                )
                result = None

            # set timeout to allow for keep alive messages
            result.settimeout(2.0)
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        return result
    
    def __unpack_server_info(self, data, packet_size, major, minor):
        offset = 0
        # Server name
        # szName = data[offset: offset+256]
        self.__application_name, separator, remainder = bytes(
            data[offset : offset + 256]
        ).partition(b"\0")
        self.__application_name = str(self.__application_name, "utf-8")
        offset += 256
        # Server Version info
        server_version = struct.unpack("BBBB", data[offset : offset + 4])
        offset += 4
        self.__server_version[0] = server_version[0]
        self.__server_version[1] = server_version[1]
        self.__server_version[2] = server_version[2]
        self.__server_version[3] = server_version[3]

        # NatNet Version info
        nnsvs = struct.unpack("BBBB", data[offset : offset + 4])
        offset += 4
        self.__nat_net_stream_version_server[0] = nnsvs[0]
        self.__nat_net_stream_version_server[1] = nnsvs[1]
        self.__nat_net_stream_version_server[2] = nnsvs[2]
        self.__nat_net_stream_version_server[3] = nnsvs[3]
        if (self.__nat_net_requested_version[0] == 0) and (
            self.__nat_net_requested_version[1] == 0
        ):
            self.__nat_net_requested_version[0] = self.__nat_net_stream_version_server[
                0
            ]
            self.__nat_net_requested_version[1] = self.__nat_net_stream_version_server[
                1
            ]
            self.__nat_net_requested_version[2] = self.__nat_net_stream_version_server[
                2
            ]
            self.__nat_net_requested_version[3] = self.__nat_net_stream_version_server[
                3
            ]
            # Determine if the bitstream version can be changed
            if (self.__nat_net_stream_version_server[0] >= 4) and (
                not self.use_multicast
            ):
                self.__can_change_bitstream_version = True

        print("Sending Application Name: ", self.__application_name)
        print(
            "NatNetVersion ",
            str(self.__nat_net_stream_version_server[0]),
            " ",
            str(self.__nat_net_stream_version_server[1]),
            " ",
            str(self.__nat_net_stream_version_server[2]),
            " ",
            str(self.__nat_net_stream_version_server[3]),
        )

        print(
            "ServerVersion ",
            str(self.__server_version[0]),
            " ",
            str(self.__server_version[1]),
            " ",
            str(self.__server_version[2]),
            " ",
            str(self.__server_version[3]),
        )
        return offset

    def __command_thread_function(self, in_socket, stop, gprint_level):
        message_id_dict = {}
        if not self.use_multicast:
            in_socket.settimeout(2.0)
        data = bytearray(0)
        # 64k buffer size
        recv_buffer_size = 64 * 1024
        while not stop():
            # Block for input
            try:
                data, addr = in_socket.recvfrom(recv_buffer_size)
            except socket.error as msg:
                if stop():
                    print(f"shutting down: {msg}")

            if len(data) > 0:
                # peek ahead at message_id
                message_id = Unpacker.get_message_id(data)
                tmp_str = "mi_%1.1d" % message_id
                if tmp_str not in message_id_dict:
                    message_id_dict[tmp_str] = 0
                message_id_dict[tmp_str] += 1

                print_level = gprint_level()
                if message_id == NAT_FRAMEOFDATA:
                    if print_level > 0:
                        if (message_id_dict[tmp_str] % print_level) == 0:
                            print_level = 1
                        else:
                            print_level = 0
                message_id = self.__process_message(data, print_level)

                data = bytearray(0)

            if not self.use_multicast:
                if not stop():
                    self.send_keep_alive(
                        in_socket, self.server_ip_address, self.command_port
                    )
        return 0

    def __data_thread_function(self, in_socket, stop):
        message_id_dict = {}
        data = bytearray(0)
        # 64k buffer size
        recv_buffer_size = 64 * 1024

        while not stop():
            # Block for input
            try:
                data, addr = in_socket.recvfrom(recv_buffer_size)
            except socket.error as msg:
                if not stop():
                    print("ERROR: data socket access error occurred:\n  %s" % msg)
                    return 1

            if len(data) > 0:
                # peek ahead at message_id
                message_id = Unpacker.get_message_id(data)
                tmp_str = "mi_%1.1d" % message_id
                if tmp_str not in message_id_dict:
                    message_id_dict[tmp_str] = 0
                message_id_dict[tmp_str] += 1

                self.__process_message(data, PRINT_LEVEL)

                data = bytearray(0)
        return 0

    def __create_data_socket(self, port):
        result = None

        if self.use_multicast:
            # Multicast case
            result = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, 0  # Internet
            )  # UDP
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            result.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                socket.inet_aton(self.multicast_address)
                + socket.inet_aton(self.local_ip_address),
            )
            try:
                result.bind((self.local_ip_address, port))
            except socket.error as msg:
                print("ERROR: data socket error occurred:\n%s" % msg)
                print(
                    "  Check Motive/Server mode requested mode agreement.  You requested Multicast "
                )
                result = None
        else:
            # Unicast case
            result = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP  # Internet
            )
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # result.bind( (self.local_ip_address, port) )
            try:
                result.bind(("", 0))
            except socket.error as msg:
                print("ERROR: data socket error occurred:\n%s" % msg)
                print(
                    "Check Motive/Server mode requested mode agreement.  You requested Unicast "
                )
                result = None

            if self.multicast_address != "255.255.255.255":
                result.setsockopt(
                    socket.IPPROTO_IP,
                    socket.IP_ADD_MEMBERSHIP,
                    socket.inet_aton(self.multicast_address)
                    + socket.inet_aton(self.local_ip_address),
                )

        return result

    def run(self):
        # Create the data socket
        self.data_socket = self.__create_data_socket(self.data_port)
        if self.data_socket is None:
            print("Could not open data channel")
            return False

        # Create the command socket
        self.command_socket = self.__create_command_socket()
        if self.command_socket is None:
            print("Could not open command channel")
            return False
        self.__is_locked = True

        self.stop_threads = False
        # Create a separate thread for receiving data packets
        self.data_thread = Thread(
            target=self.__data_thread_function,
            args=(
                self.data_socket,
                lambda: self.stop_threads,
            ),
        )
        self.data_thread.start()

        # Create a separate thread for receiving command packets
        self.command_thread = Thread(
            target=self.__command_thread_function,
            args=(
                self.command_socket,
                lambda: self.stop_threads,
                lambda: PRINT_LEVEL,
            ),
        )
        self.command_thread.start()

        # Required for setup
        # Get NatNet and server versions
        self.send_request(
            self.command_socket,
            NAT_CONNECT,
            "",
            (self.server_ip_address, self.command_port),
        )

        # Example Commands
        # Get NatNet and server versions
        # self.send_request(self.command_socket, NAT_CONNECT, "", (self.server_ip_address, self.command_port) )
        # Request the model definitions
        # self.send_request(self.command_socket, NAT_REQUEST_MODELDEF, "",  (self.server_ip_address, self.command_port) )
        return True

    def send_request(self, in_socket, command, command_str, address):
        # Compose the message in our known message format
        packet_size = 0
        if (
            command == NAT_REQUEST_MODELDEF
            or command == NAT_REQUEST_FRAMEOFDATA
        ):
            packet_size = 0
            command_str = ""
        elif command == NAT_REQUEST:
            packet_size = len(command_str) + 1
        elif command == NAT_CONNECT:
            command_str = "Ping"
            packet_size = len(command_str) + 1
        elif command == NAT_KEEPALIVE:
            packet_size = 0
            command_str = ""

        data = command.to_bytes(2, byteorder="little")
        data += packet_size.to_bytes(2, byteorder="little")

        data += command_str.encode("utf-8")
        data += b"\0"

        return in_socket.sendto(data, address)

    def get_major(self):
        return self.__nat_net_requested_version[0]

    def get_minor(self):
        return self.__nat_net_requested_version[1]

    def __process_message(self, data: bytes, print_level=0):
        # return message ID
        major = self.get_major()
        minor = self.get_minor()

        print("Begin Packet\n-----------------")
        show_nat_net_version = False
        if show_nat_net_version:
            print(
                "NatNetVersion ",
                str(self.__nat_net_requested_version[0]),
                " ",
                str(self.__nat_net_requested_version[1]),
                " ",
                str(self.__nat_net_requested_version[2]),
                " ",
                str(self.__nat_net_requested_version[3]),
            )

        message_id = Unpacker(self.rigid_body_listener, self.new_frame_listener).unpack(data, major, minor)
        return message_id
