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

def get_message_id(data):
    message_id = int.from_bytes(data[0:2], byteorder="little")
    return message_id

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
            except socket.herror:
                print("ERROR: command socket herror occurred")
                result = None
            except socket.gaierror:
                print("ERROR: command socket gaierror occurred")
                result = None
            except socket.timeout:
                print("ERROR: command socket timeout occurred. Server not responding")
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
            except socket.herror:
                print("ERROR: command socket herror occurred")
                result = None
            except socket.gaierror:
                print("ERROR: command socket gaierror occurred")
                result = None
            except socket.timeout:
                print("ERROR: command socket timeout occurred. Server not responding")
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

    def __unpack_frame_prefix_data(self, data):
        offset = 0
        # Frame number (4 bytes)
        frame_number = int.from_bytes(data[offset : offset + 4], byteorder="little")
        offset += 4
        print("Frame #:", frame_number)
        frame_prefix_data = MoCapData.FramePrefixData(frame_number)
        return offset, frame_prefix_data

    def __unpack_marker_set_data(self, data, packet_size, major, minor):
        marker_set_data = MoCapData.MarkerSetData()
        offset = 0
        # Marker set count (4 bytes)
        marker_set_count = int.from_bytes(data[offset : offset + 4], byteorder="little")
        offset += 4
        print("Marker Set Count:", marker_set_count)

        for i in range(0, marker_set_count):
            marker_data = MoCapData.MarkerData()
            # Model name
            model_name, separator, remainder = bytes(data[offset:]).partition(b"\0")
            offset += len(model_name) + 1
            print("Model Name      : ", model_name.decode("utf-8"))
            marker_data.set_model_name(model_name)
            # Marker count (4 bytes)
            marker_count = int.from_bytes(data[offset : offset + 4], byteorder="little")
            offset += 4
            print("Marker Count    : ", marker_count)

            for j in range(0, marker_count):
                pos = Vector3.unpack(data[offset : offset + 12])
                offset += 12
                print(
                    "\tMarker %3.1d : [%3.2f,%3.2f,%3.2f]" % (j, pos[0], pos[1], pos[2])
                )
                marker_data.add_pos(pos)
            marker_set_data.add_marker_data(marker_data)

        # Unlabeled markers count (4 bytes)
        unlabeled_markers_count = int.from_bytes(
            data[offset : offset + 4], byteorder="little"
        )
        offset += 4
        print("Unlabeled Markers Count:", unlabeled_markers_count)

        for i in range(0, unlabeled_markers_count):
            pos = Vector3.unpack(data[offset : offset + 12])
            offset += 12
            print(
                "\tMarker %3.1d : [%3.2f,%3.2f,%3.2f]" % (i, pos[0], pos[1], pos[2])
            )
            marker_set_data.add_unlabeled_marker(pos)
        return offset, marker_set_data

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
                    # print("ERROR: command socket access error occurred:\n  %s" %msg)
                    # return 1
                    print(f"shutting down: {msg}")
            except socket.herror:
                print("ERROR: command socket access herror occurred")
                return 2
            except socket.gaierror:
                print("ERROR: command socket access gaierror occurred")
                return 3
            except socket.timeout:
                if self.use_multicast:
                    print(
                        "ERROR: command socket access timeout occurred. Server not responding"
                    )
                    # return 4

            if len(data) > 0:
                # peek ahead at message_id
                message_id = get_message_id(data)
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

    def __data_thread_function(self, in_socket, stop, gprint_level):
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
            except socket.herror:
                print("ERROR: data socket access herror occurred")
                # return 2
            except socket.gaierror:
                print("ERROR: data socket access gaierror occurred")
                # return 3
            except socket.timeout:
                # if self.use_multicast:
                print(
                    "ERROR: data socket access timeout occurred. Server not responding"
                )
                # return 4
            if len(data) > 0:
                # peek ahead at message_id
                message_id = get_message_id(data)
                tmp_str = "mi_%1.1d" % message_id
                if tmp_str not in message_id_dict:
                    message_id_dict[tmp_str] = 0
                message_id_dict[tmp_str] += 1

                # print_level = gprint_level()
                # if message_id == NAT_FRAMEOFDATA:
                #     if print_level > 0:
                #         if (message_id_dict[tmp_str] % print_level) == 0:
                #             print_level = 1
                #         else:
                #             print_level = 0
                message_id = self.__process_message(data, PRINT_LEVEL)

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
            except socket.herror:
                print("ERROR: data socket herror occurred")
                result = None
            except socket.gaierror:
                print("ERROR: data socket gaierror occurred")
                result = None
            except socket.timeout:
                print("ERROR: data socket timeout occurred. Server not responding")
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
            except socket.herror:
                print("ERROR: data socket herror occurred")
                result = None
            except socket.gaierror:
                print("ERROR: data socket gaierror occurred")
                result = None
            except socket.timeout:
                print("ERROR: data socket timeout occurred. Server not responding")
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
                lambda: PRINT_LEVEL,
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

        message_id = get_message_id(data)

        packet_size = int.from_bytes(data[2:4], byteorder="little")

        # skip the 4 bytes for message ID and packet_size
        offset = 4
        if message_id == NAT_FRAMEOFDATA:
            print("Message ID  : %3.1d NAT_FRAMEOFDATA" % message_id)
            print("Packet Size : ", packet_size)

            offset_tmp, mocap_data = self.__unpack_mocap_data(
                data[offset:], packet_size, major, minor
            )
            offset += offset_tmp
            # get a string version of the data for output
            mocap_data_str = mocap_data.get_as_string()
            if print_level >= 1:
                print("MoCap Frame: %d\n" % (mocap_data.prefix_data.frame_number))
                print("%s\n" % mocap_data_str)

        elif message_id == NAT_MODELDEF:
            print("Message ID  : %3.1d NAT_MODELDEF" % message_id)
            print("Packet Size : %d" % packet_size)
            offset_tmp, data_descs = self.__unpack_data_descriptions(
                data[offset:], packet_size, major, minor
            )
            offset += offset_tmp
            # get a string version of the data for output
            data_descs_str = data_descs.get_as_string()
            if print_level > 0:
                print("Data Descriptions:\n")
                print("%s\n" % (data_descs_str))

        elif message_id == NAT_SERVERINFO:
            print("Message ID  : %3.1d NAT_SERVERINFO" % message_id)
            print("Packet Size : ", packet_size)
            offset += self.__unpack_server_info(
                data[offset:], packet_size, major, minor
            )

        elif message_id == NAT_RESPONSE:
            print("Message ID  : %3.1d NAT_RESPONSE" % message_id)
            print("Packet Size : ", packet_size)
            if packet_size == 4:
                command_response = int.from_bytes(
                    data[offset : offset + 4], byteorder="little"
                )
                offset += 4
                print("Command response: %d" % command_response)
            else:
                show_remainder = False
                message, separator, remainder = bytes(data[offset:]).partition(b"\0")
                offset += len(message) + 1
                if show_remainder:
                    print(
                        "Command response:",
                        message.decode("utf-8"),
                        " separator:",
                        separator,
                        " remainder:",
                        remainder,
                    )
                else:
                    print("Command response:", message.decode("utf-8"))
        elif message_id == NAT_UNRECOGNIZED_REQUEST:
            print("Message ID  : %3.1d NAT_UNRECOGNIZED_REQUEST: " % message_id)
            print("Packet Size : ", packet_size)
            print("Received 'Unrecognized request' from server")
        elif message_id == NAT_MESSAGESTRING:
            print("Message ID  : %3.1d NAT_MESSAGESTRING" % message_id)
            print("Packet Size : ", packet_size)
            message, separator, remainder = bytes(data[offset:]).partition(b"\0")
            offset += len(message) + 1
            print("Received message from server:", message.decode("utf-8"))
        else:
            print("Message ID  : %3.1d UNKNOWN" % message_id)
            print("Packet Size : ", packet_size)
            print("ERROR: Unrecognized packet type")

        print("End Packet\n-----------------")
        return message_id

    def __unpack_rigid_body(self, data, major, minor, rb_num):
        offset = 0

        # ID (4 bytes)
        new_id = int.from_bytes(data[offset : offset + 4], byteorder="little")
        offset += 4

        print("RB: %3.1d ID: %3.1d" % (rb_num, new_id))

        # Position and orientation
        pos = Vector3.unpack(data[offset : offset + 12])
        offset += 12
        print("\tPosition    : [%3.2f, %3.2f, %3.2f]" % (pos[0], pos[1], pos[2]))

        rot = Quaternion.unpack(data[offset : offset + 16])
        offset += 16
        print(
            "\tOrientation : [%3.2f, %3.2f, %3.2f, %3.2f]"
            % (rot[0], rot[1], rot[2], rot[3])
        )

        rigid_body = MoCapData.RigidBody(new_id, pos, rot)

        # Send information to any listener.
        if self.rigid_body_listener is not None:
            self.rigid_body_listener(new_id, pos, rot)

            # RB Marker Data ( Before version 3.0.  After Version 3.0 Marker data is in description )
            if major < 3 and major != 0:
                # Marker count (4 bytes)
                marker_count = int.from_bytes(data[offset: offset + 4], byteorder="little")
                offset += 4
                marker_count_range = range(0, marker_count)
                print("\tMarker Count:", marker_count)

                rb_marker_list = []
                for i in marker_count_range:
                    rb_marker_list.append(MoCapData.RigidBodyMarker())

                # Marker positions
                for i in marker_count_range:
                    pos = Vector3.unpack(data[offset: offset + 12])
                    offset += 12
                    print("\tMarker", i, ":", pos[0], ",", pos[1], ",", pos[2])
                    rb_marker_list[i].pos = pos

                if major >= 2:
                    # Marker ID's
                    for i in marker_count_range:
                        new_id = int.from_bytes(
                            data[offset: offset + 4], byteorder="little"
                        )
                        offset += 4
                        print("\tMarker ID", i, ":", new_id)
                        rb_marker_list[i].id = new_id

                    # Marker sizes
                    for i in marker_count_range:
                        size = FloatValue.unpack(data[offset: offset + 4])
                        offset += 4
                        print("\tMarker Size", i, ":", size[0])
                        rb_marker_list[i].size = size

                for i in marker_count_range:
                    rigid_body.add_rigid_body_marker(rb_marker_list[i])
            if major >= 2:
                (marker_error,) = FloatValue.unpack(data[offset: offset + 4])
                offset += 4
                print("\tMarker Error: %3.2f" % marker_error)
                rigid_body.error = marker_error

            # Version 2.6 and later
            if ((major == 2) and (minor >= 6)) or major > 2:
                (param,) = struct.unpack("h", data[offset: offset + 2])
                tracking_valid = (param & 0x01) != 0
                offset += 2
                is_valid_str = "False"
                if tracking_valid:
                    is_valid_str = "True"
                print("\tTracking Valid: %s" % is_valid_str)
                if tracking_valid:
                    rigid_body.tracking_valid = True
                else:
                    rigid_body.tracking_valid = False

            return offset, rigid_body

    def __unpack_skeleton_data(self, data, packet_size, major, minor):
        skeleton_data = MoCapData.SkeletonData()

        offset = 0
        # Version 2.1 and later
        skeleton_count = 0
        if (major == 2 and minor > 0) or major > 2:
            skeleton_count = int.from_bytes(
                data[offset : offset + 4], byteorder="little"
            )
            offset += 4
            print("Skeleton Count:", skeleton_count)
            for _ in range(0, skeleton_count):
                rel_offset, skeleton = self.__unpack_skeleton(
                    data[offset:], major, minor
                )
                offset += rel_offset
                skeleton_data.add_skeleton(skeleton)

        return offset, skeleton_data
    
    def __unpack_labeled_marker_data(self, data, packet_size, major, minor):
        labeled_marker_data = MoCapData.LabeledMarkerData()
        offset = 0
        # Labeled markers (Version 2.3 and later)
        labeled_marker_count = 0
        if (major == 2 and minor > 3) or major > 2:
            labeled_marker_count = int.from_bytes(
                data[offset : offset + 4], byteorder="little"
            )
            offset += 4
            print("Labeled Marker Count:", labeled_marker_count)
            for _ in range(0, labeled_marker_count):
                model_id = 0
                marker_id = 0
                tmp_id = int.from_bytes(data[offset : offset + 4], byteorder="little")
                offset += 4
                model_id, marker_id = self.__decode_marker_id(tmp_id)
                pos = Vector3.unpack(data[offset : offset + 12])
                offset += 12
                size = FloatValue.unpack(data[offset : offset + 4])
                offset += 4
                print(
                    "ID     : [MarkerID: %3.1d] [ModelID: %3.1d]"
                    % (marker_id, model_id)
                )
                print("  pos  : [%3.2f, %3.2f, %3.2f]" % (pos[0], pos[1], pos[2]))
                print("  size : [%3.2f]" % size)

                # Version 2.6 and later
                param = 0
                if (major == 2 and minor >= 6) or major > 2:
                    (param,) = struct.unpack("h", data[offset : offset + 2])
                    offset += 2
                    # occluded = ( param & 0x01 ) != 0
                    # point_cloud_solved = ( param & 0x02 ) != 0
                    # model_solved = ( param & 0x04 ) != 0

                # Version 3.0 and later
                residual = 0.0
                if major >= 3:
                    (residual,) = FloatValue.unpack(data[offset : offset + 4])
                    offset += 4
                    print("  err  : [%3.2f]" % residual)

                labeled_marker = MoCapData.LabeledMarker(
                    tmp_id, pos, size, param, residual
                )
                labeled_marker_data.add_labeled_marker(labeled_marker)

        return offset, labeled_marker_data
    
    def __unpack_force_plate_data(self, data, packet_size, major, minor):
        force_plate_data = MoCapData.ForcePlateData()
        n_frames_show_max = 4
        offset = 0
        # Force Plate data (version 2.9 and later)
        force_plate_count = 0
        if (major == 2 and minor >= 9) or major > 2:
            force_plate_count = int.from_bytes(
                data[offset : offset + 4], byteorder="little"
            )
            offset += 4
            print("Force Plate Count:", force_plate_count)
            for i in range(0, force_plate_count):
                # ID
                force_plate_id = int.from_bytes(
                    data[offset : offset + 4], byteorder="little"
                )
                offset += 4
                force_plate = MoCapData.ForcePlate(force_plate_id)

                # Channel Count
                force_plate_channel_count = int.from_bytes(
                    data[offset : offset + 4], byteorder="little"
                )
                offset += 4

                print(
                    "\tForce Plate %3.1d ID: %3.1d Num Channels: %3.1d"
                    % (i, force_plate_id, force_plate_channel_count)
                )

                # Channel Data
                for j in range(force_plate_channel_count):
                    fp_channel_data = MoCapData.ForcePlateChannelData()
                    force_plate_channel_frame_count = int.from_bytes(
                        data[offset : offset + 4], byteorder="little"
                    )
                    offset += 4
                    out_string = "\tChannel %3.1d: " % (j)
                    out_string += "  %3.1d Frames - Frame Data: " % (
                        force_plate_channel_frame_count
                    )

                    # Force plate frames
                    n_frames_show = min(
                        force_plate_channel_frame_count, n_frames_show_max
                    )
                    for k in range(force_plate_channel_frame_count):
                        force_plate_channel_val = FloatValue.unpack(
                            data[offset : offset + 4]
                        )
                        offset += 4
                        fp_channel_data.add_frame_entry(force_plate_channel_val)

                        if k < n_frames_show:
                            out_string += "%3.2f " % (force_plate_channel_val)
                    if n_frames_show < force_plate_channel_frame_count:
                        out_string += " showing %3.1d of %3.1d frames" % (
                            n_frames_show,
                            force_plate_channel_frame_count,
                        )
                    print("%s" % out_string)
                    force_plate.add_channel_data(fp_channel_data)
                force_plate_data.add_force_plate(force_plate)
        return offset, force_plate_data
    
    def __unpack_device_data(self, data, packet_size, major, minor):
        device_data = MoCapData.DeviceData()
        n_frames_show_max = 4
        offset = 0
        # Device data (version 2.11 and later)
        device_count = 0
        if (major == 2 and minor >= 11) or (major > 2):
            device_count = int.from_bytes(data[offset : offset + 4], byteorder="little")
            offset += 4
            print("Device Count:", device_count)
            for i in range(0, device_count):

                # ID
                device_id = int.from_bytes(
                    data[offset : offset + 4], byteorder="little"
                )
                offset += 4
                device = MoCapData.Device(device_id)
                # Channel Count
                device_channel_count = int.from_bytes(
                    data[offset : offset + 4], byteorder="little"
                )
                offset += 4

                print(
                    "\tDevice %3.1d      ID: %3.1d Num Channels: %3.1d"
                    % (i, device_id, device_channel_count)
                )

                # Channel Data
                for j in range(0, device_channel_count):
                    device_channel_data = MoCapData.DeviceChannelData()
                    device_channel_frame_count = int.from_bytes(
                        data[offset : offset + 4], byteorder="little"
                    )
                    offset += 4
                    out_string = "\tChannel %3.1d " % (j)
                    out_string += "  %3.1d Frames - Frame Data: " % (
                        device_channel_frame_count
                    )

                    # Device Frame Data
                    n_frames_show = min(device_channel_frame_count, n_frames_show_max)
                    for k in range(0, device_channel_frame_count):
                        device_channel_val = int.from_bytes(
                            data[offset : offset + 4], byteorder="little"
                        )
                        device_channel_val = FloatValue.unpack(
                            data[offset : offset + 4]
                        )
                        offset += 4
                        if k < n_frames_show:
                            out_string += "%3.2f " % (device_channel_val)

                        device_channel_data.add_frame_entry(device_channel_val)
                    if n_frames_show < device_channel_frame_count:
                        out_string += " showing %3.1d of %3.1d frames" % (
                            n_frames_show,
                            device_channel_frame_count,
                        )
                    print("%s" % out_string)
                    device.add_channel_data(device_channel_data)
                device_data.add_device(device)
        return offset, device_data

    def __unpack_rigid_body_data(self, data, packet_size, major, minor):
        rigid_body_data = MoCapData.RigidBodyData()
        offset = 0
        # Rigid body count (4 bytes)
        rigid_body_count = int.from_bytes(data[offset : offset + 4], byteorder="little")
        offset += 4
        print("Rigid Body Count:", rigid_body_count)

        for i in range(0, rigid_body_count):
            offset_tmp, rigid_body = self.__unpack_rigid_body(
                data[offset:], major, minor, i
            )
            offset += offset_tmp
            rigid_body_data.add_rigid_body(rigid_body)

        return offset, rigid_body_data

    def __unpack_frame_suffix_data(self, data, packet_size, major, minor):
        frame_suffix_data = MoCapData.FrameSuffixData()
        offset = 0

        # Timecode
        timecode = int.from_bytes(data[offset : offset + 4], byteorder="little")
        offset += 4
        frame_suffix_data.timecode = timecode

        timecode_sub = int.from_bytes(data[offset : offset + 4], byteorder="little")
        offset += 4
        frame_suffix_data.timecode_sub = timecode_sub

        # Timestamp (increased to double precision in 2.7 and later)
        if (major == 2 and minor >= 7) or (major > 2):
            (timestamp,) = DoubleValue.unpack(data[offset : offset + 8])
            offset += 8
        else:
            (timestamp,) = FloatValue.unpack(data[offset : offset + 4])
            offset += 4
        print("Timestamp : %3.2f" % timestamp)
        frame_suffix_data.timestamp = timestamp

        # Hires Timestamp (Version 3.0 and later)
        if major >= 3:
            stamp_camera_mid_exposure = int.from_bytes(
                data[offset : offset + 8], byteorder="little"
            )
            print(
                "Mid-exposure timestamp         : %3.1d" % stamp_camera_mid_exposure
            )
            offset += 8
            frame_suffix_data.stamp_camera_mid_exposure = stamp_camera_mid_exposure

            stamp_data_received = int.from_bytes(
                data[offset : offset + 8], byteorder="little"
            )
            offset += 8
            frame_suffix_data.stamp_data_received = stamp_data_received
            print("Camera data received timestamp : %3.1d" % stamp_data_received)

            stamp_transmit = int.from_bytes(
                data[offset : offset + 8], byteorder="little"
            )
            offset += 8
            print("Transmit timestamp             : %3.1d" % stamp_transmit)
            frame_suffix_data.stamp_transmit = stamp_transmit

        # Frame parameters
        (param,) = struct.unpack("h", data[offset : offset + 2])
        is_recording = (param & 0x01) != 0
        tracked_models_changed = (param & 0x02) != 0
        offset += 2
        frame_suffix_data.param = param
        frame_suffix_data.is_recording = is_recording
        frame_suffix_data.tracked_models_changed = tracked_models_changed

        return offset, frame_suffix_data

    def __unpack_mocap_data(self, data: bytes, packet_size, major, minor):
        mocap_data = MoCapData.MoCapData()
        print("MoCap Frame Begin\n-----------------")
        data = memoryview(data)
        offset = 0
        rel_offset = 0

        # Frame Prefix Data
        rel_offset, frame_prefix_data = self.__unpack_frame_prefix_data(data[offset:])
        offset += rel_offset
        mocap_data.set_prefix_data(frame_prefix_data)
        frame_number = frame_prefix_data.frame_number

        # Marker Set Data
        rel_offset, marker_set_data = self.__unpack_marker_set_data(
            data[offset:], (packet_size - offset), major, minor
        )
        offset += rel_offset
        mocap_data.set_marker_set_data(marker_set_data)
        marker_set_count = marker_set_data.get_marker_set_count()
        unlabeled_markers_count = marker_set_data.get_unlabeled_marker_count()

        # Rigid Body Data
        rel_offset, rigid_body_data = self.__unpack_rigid_body_data(
            data[offset:], (packet_size - offset), major, minor
        )
        offset += rel_offset
        mocap_data.set_rigid_body_data(rigid_body_data)
        rigid_body_count = rigid_body_data.get_rigid_body_count()

        # Skeleton Data
        rel_offset, skeleton_data = self.__unpack_skeleton_data(
            data[offset:], (packet_size - offset), major, minor
        )
        offset += rel_offset
        mocap_data.set_skeleton_data(skeleton_data)
        skeleton_count = skeleton_data.get_skeleton_count()

        # Labeled Marker Data
        rel_offset, labeled_marker_data = self.__unpack_labeled_marker_data(
            data[offset:], (packet_size - offset), major, minor
        )
        offset += rel_offset
        mocap_data.set_labeled_marker_data(labeled_marker_data)
        labeled_marker_count = labeled_marker_data.get_labeled_marker_count()

        # Force Plate Data
        rel_offset, force_plate_data = self.__unpack_force_plate_data(
            data[offset:], (packet_size - offset), major, minor
        )
        offset += rel_offset
        mocap_data.set_force_plate_data(force_plate_data)

        # Device Data
        rel_offset, device_data = self.__unpack_device_data(
            data[offset:], (packet_size - offset), major, minor
        )
        offset += rel_offset
        mocap_data.set_device_data(device_data)

        # Frame Suffix Data
        # rel_offset, timecode, timecode_sub, timestamp, is_recording, tracked_models_changed = \
        rel_offset, frame_suffix_data = self.__unpack_frame_suffix_data(
            data[offset:], (packet_size - offset), major, minor
        )
        offset += rel_offset
        mocap_data.set_suffix_data(frame_suffix_data)

        timecode = frame_suffix_data.timecode
        stamp_data_received = frame_suffix_data.stamp_data_received
        timecode_sub = frame_suffix_data.timecode_sub
        timestamp = frame_suffix_data.timestamp
        is_recording = frame_suffix_data.is_recording
        tracked_models_changed = frame_suffix_data.tracked_models_changed
        # Send information to any listener.
        if self.new_frame_listener is not None:
            data_dict = {}
            data_dict["frame_number"] = frame_number
            data_dict["marker_set_count"] = marker_set_count
            data_dict["unlabeled_markers_count"] = unlabeled_markers_count
            data_dict["rigid_body_count"] = rigid_body_count
            data_dict["skeleton_count"] = skeleton_count
            data_dict["labeled_marker_count"] = labeled_marker_count
            data_dict["timecode"] = timecode
            data_dict["timecode_sub"] = timecode_sub
            data_dict["timestamp"] = timestamp
            data_dict["is_recording"] = is_recording
            data_dict["tracked_models_changed"] = tracked_models_changed
            data_dict["stamp_data_received"] = stamp_data_received

            self.new_frame_listener(data_dict)
        print("MoCap Frame End\n-----------------")
        return offset, mocap_data