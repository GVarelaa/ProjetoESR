import pickle
import io
from datetime import datetime

class Message:
    def __init__(self, msg_type, flag=0, timestamp=0, neighbours=None, jumps=None):
        # Header
        self.type = msg_type
        self.flag = flag
        self.timestamp = timestamp
        # Data
        self.neighbours = neighbours
        self.jumps = jumps
    
    def __str__(self):
        return f"Type: {self.type} | Flag: {self.flag} | Timestamp: {self.timestamp} | Neighbours: {self.neighbours} | Jumps: {self.jumps}"

    def __repr__(self):
        return f"Type: {self.type} | Flag: {self.flag} | Timestamp: {self.timestamp} | Neighbours: {self.neighbours} | Jumps: {self.jumps}"

    def serialize(self):
        # Header
        dictionary = { 
            "type": self.type,
            "flag": self.flag,
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

        message = Message(dictionary["type"], flag=dictionary["flag"], timestamp=dictionary["timestamp"])

        if "neighbours" in dictionary:
            message.neighbours = dictionary["neighbours"]
        
        elif "jumps" in dictionary:
            message.jumps = dictionary["jumps"]
        
        return message
    