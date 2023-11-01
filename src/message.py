import pickle
from datetime import datetime

class Message:
    def __init__(self, msg_type, timestamp=None, flags=None, jumps=None):
        # Header
        self.type = msg_type
        self.flags = flags
        # Data
        self.timestamp = timestamp
        self.jumps = jumps

    
    def __str__(self):
        return f"type: {self.type}"

    def __repr__(self):
        return f"type: {self.type}"

    def serialize(self):
        # type - 1 byte
        byte_array = bytearray()
        
        byte_array.append(self.type.to_bytes(1, 'big'))

        timestamp = self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        byte_array.append(len(timestamp).to_bytes(1, 'big'))
        byte_array.append(timestamp.encode('utf-8'))
        
        byte_array.append(pickle.dumps(self.jumps))

        return byte_array

    @staticmethod
    def deserialize(bytes):
        msg_type = int(bytes[0])

        timestamp_num = int(bytes[1])
        timestamp = bytes[2:2+timestamp_num].decode('utf-8')

        jumps = pickle.loads(bytes[2+timestamp_num+1])

        return Message(msg_type, timestamp=timestamp, jumps=jumps)
    