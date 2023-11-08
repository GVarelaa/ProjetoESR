import pickle
import io
from datetime import datetime

class Message:
    def __init__(self, msg_type, flag=0, timestamp=0, source_ip="", hops=None, neighbours=None, contents=None):
        # Header
        self.type = msg_type
        self.flag = flag
        self.timestamp = timestamp
        # Data
        self.data = data

    
    def __str__(self):
        return f"Type: {self.type} | Flag: {self.flag} | Timestamp: {self.timestamp} | Source IP: {self.source_ip} | Hops: {self.hops} | Neighbours: {self.neighbours} | Contents: {self.contents}"


    def __repr__(self):
        return f"Type: {self.type} | Flag: {self.flag} | Timestamp: {self.timestamp} | Source IP: {self.source_ip} | Hops: {self.hops} | Neighbours: {self.neighbours} | Contents: {self.contents}"


    def serialize(self):
        byte_array = bytearray()

        # Header
        # Type - 1 byte
        byte_array += self.type.to_bytes(1, 'big')

        # Flags - 1 byte
        byte_array += self.flag.to_bytes(1, 'big')

        # Timestamp - 8 bytes
        byte_array += self.timestamp.to_bytes(8, 'big')

        # Number of hops - 1 bytes
        byte_array += len(self.hop).to_bytes(1, 'big')

        # Number of neighbours - 1 bytes
        byte_array += len(self.neighbours).to_bytes(1, 'big')

        # Number of contents - 1 bytes
        byte_array += len(self.contents).to_bytes(1, 'big')
        
        # Data
        # Source IP
        byte_array += len(self.source_ip).to_bytes(1, 'big')
        byte_array += self.source_ip.encode('utf-8')
        
        # Hops
        for hop in self.hops:
            # Tamanho string hop - 1 byte
            byte_array += len(hop).to_bytes(1, 'big')
            byte_array += hop.encode('utf-8')

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
        flags = int.from_bytes(byte_array.read(1), byteorder='big')
        timestamp = float.from_bytes(byte_array.read(8), byteorder='big')

        nr_hops = int.from_bytes(byte_array.read(1), byteorder='big')
        nr_neighbours = int.from_bytes(byte_array.read(1), byteorder='big')
        nr_contents = int.from_bytes(byte_array.read(1), byteorder='big')

        hops = list()
        neighbours = list()
        contents = list()

        for _ in range(nr_hops):
            string_len = int.from_bytes(byte_array.read(1), byteorder='big')
            hops.append(byte_array.read(string_len).decode('utf-8'))

        for _ in range(nr_neighbours):
            string_len = int.from_bytes(byte_array.read(1), byteorder='big')
            hops.append(byte_array.read(string_len).decode('utf-8'))

        for _ in range(nr_contents)
            string_len = int.from_bytes(byte_array.read(1), byteorder='big')
            contents.append(byte_array.read(string_len).decode('utf-8'))
        
        return Message(msg_type, flag=flags, timestamp=timestamp, source_ip=source_ip, hops=hops, neighbours=neighbours, contents=contents)
    