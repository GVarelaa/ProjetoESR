import io
import struct

class ControlPacket:
    NEIGHBOURS = 0
    STATUS = 1
    PLAY = 2
    PAUSE = 3
    LEAVE = 4

    def __init__(self, msg_type, response=0, error=0, latency=0, hops=list(), neighbours=list(), contents=list(), servers=list()):
        # Header
        self.type = msg_type
        self.response = response #Alterar para bit
        self.error = error #Alterar para bit
        self.latency = latency
        # Data
        self.hops = hops
        self.servers = servers
        self.neighbours = neighbours
        self.contents = contents

    
    def __str__(self):
        return f"Type: {self.type} | Response: {self.response} | Error: {self.error} | Latency: {self.latency} | Hops: {self.hops} | Servers: {self.servers} | Neighbours: {self.neighbours} | Contents: {self.contents}"


    def __repr__(self):
        return f"Type: {self.type} | Response: {self.response} | Error: {self.error} | Latency: {self.latency} | Hops: {self.hops} | Servers: {self.servers} | Neighbours: {self.neighbours} | Contents: {self.contents}"


    def serialize(self):
        byte_array = bytearray()

        # Header
        # Type - 1 byte
        byte_array += self.type.to_bytes(1, 'big')

        # Response - 1 byte
        byte_array += self.response.to_bytes(1, 'big')

        # Error - 1 byte
        byte_array += self.error.to_bytes(1, 'big')

        # Latency - 8 bytes
        byte_array += struct.pack('>d', self.latency)

        # Number of hops - 1 bytes
        byte_array += len(self.hops).to_bytes(1, 'big')

        # Number of servers - 1 bytes
        byte_array += len(self.servers).to_bytes(1, 'big')

        # Number of neighbours - 1 bytes
        byte_array += len(self.neighbours).to_bytes(1, 'big')

        # Number of contents - 1 bytes
        byte_array += len(self.contents).to_bytes(1, 'big')
        
        # Data
        # Hops
        for hop in self.hops:
            # Tamanho string hop - 1 byte
            byte_array += len(hop).to_bytes(1, 'big')
            byte_array += hop.encode('utf-8')
        
        # Servers
        for server in self.servers:
            # Tamanho string server - 1 byte
            byte_array += len(server).to_bytes(1, 'big')
            byte_array += server.encode('utf-8')

        # Neighbours
        for neighbour in self.neighbours:
            # Tamanho string content - 1 byte
            byte_array += len(neighbour).to_bytes(1, 'big')
            byte_array += neighbour.encode('utf-8')

        # Contents
        for content in self.contents:
            # Tamanho string content - 1 byte
            byte_array += len(content).to_bytes(1, 'big')
            byte_array += content.encode('utf-8')

        return byte_array

    @staticmethod
    def deserialize(bytes):
        byte_array = io.BytesIO(bytes)

        msg_type = int.from_bytes(byte_array.read(1), byteorder='big')
        response = int.from_bytes(byte_array.read(1), byteorder='big')
        error = int.from_bytes(byte_array.read(1), byteorder='big')
        latency = struct.unpack('>d', byte_array.read(8))[0]

        nr_hops = int.from_bytes(byte_array.read(1), byteorder='big')
        nr_servers = int.from_bytes(byte_array.read(1), byteorder='big')
        nr_neighbours = int.from_bytes(byte_array.read(1), byteorder='big')
        nr_contents = int.from_bytes(byte_array.read(1), byteorder='big')

        hops = list()
        servers = list()
        neighbours = list()
        contents = list()

        for _ in range(nr_hops):
            string_len = int.from_bytes(byte_array.read(1), byteorder='big')
            hops.append(byte_array.read(string_len).decode('utf-8'))

        for _ in range(nr_servers):
            string_len = int.from_bytes(byte_array.read(1), byteorder='big')
            servers.append(byte_array.read(string_len).decode('utf-8'))

        for _ in range(nr_neighbours):
            string_len = int.from_bytes(byte_array.read(1), byteorder='big')
            neighbours.append(byte_array.read(string_len).decode('utf-8'))

        for _ in range(nr_contents):
            string_len = int.from_bytes(byte_array.read(1), byteorder='big')
            contents.append(byte_array.read(string_len).decode('utf-8'))
        
        return ControlPacket(msg_type, response=response, error=error, latency=latency, hops=hops, servers=servers, neighbours=neighbours, contents=contents)
    