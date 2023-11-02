import pickle
import io
from datetime import datetime

class Message:
    def __init__(self, msg_type, flags=None, timestamp=0, neighbours=None, jumps=None):
        # Header
        self.type = msg_type
        self.flags = flags
        self.timestamp = timestamp
        # Data
        self.neighbours = neighbours
        self.jumps = jumps
    
    def __str__(self):
        return f"Type: {self.type} | Timestamp: {self.timestamp} | Neighbours: {self.neighbours} | Jumps: {self.jumps}"

    def __repr__(self):
        return f"Type: {self.type} | Timestamp: {self.timestamp} | Neighbours: {self.neighbours} | Jumps: {self.jumps}"

    def serialize(self):
        # Header
        dictionary = { 
            "type": self.type, 
            "timestamp": self.timestamp
        }

        # Data
        if self.neighbours is not None:
            dictionary["neighbours"] = self.neighbours

        if self.jumps is not None:
            dictionary["jumps"] = self.jumps

        return pickle.dumps(dictionary)

    @staticmethod
    def deserialize(bytes):
        dictionary = pickle.loads(bytes)

        message = Message(dictionary["type"], timestamp=dictionary["timestamp"])

        if "neighbours" in dictionary:
            message.neighbours = dictionary["neighbours"]
        
        elif "jumps" in dictionary:
            message.jumps = dictionary["jumps"]
        
        return message
    