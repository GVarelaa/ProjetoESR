import pickle
import io
from datetime import datetime

class Message:
    def __init__(self, msg_type, flags=None, timestamp=0, nr_neighbours=0, nr_interfaces=0, nr_jumps=0, neighbours=None, interfaces=None, jumps=None):
        # Header
        self.type = msg_type
        self.flags = flags
        self.timestamp = timestamp
        self.nr_neighbours = nr_neighbours
        self.nr_interfaces = nr_interfaces
        self.nr_jumps = nr_jumps
        # Data
        self.neighbours = neighbours
        self.interfaces = interfaces
        self.jumps = jumps
    
    def __str__(self):
        return f"type: {self.type}"

    def __repr__(self):
        return f"type: {self.type}"

    def serialize(self):
        # Header
        dictionary = { 
            "type": self.type, 
            "timestamp": self.timestamp,
            "nr_neighbours": self.nr_neighbours,
            "nr_interfaces": self.nr_interfaces,
            "nr_jumps": self.nr_jumps
        }

        # Data
        if self.neighbours is not None:
            dictionary["neighbours"] = self.neighbours
            dictionary["interfaces"] = self.interfaces

        if self.jumps is not None:
            dictionary["jumps"] = self.jumps

        return pickle.dumps(dictionary)

    @staticmethod
    def deserialize(bytes):
        dictionary = pickle.loads(bytes)

        message = Message(dictionary["type"], 
                    timestamp=dictionary["timestamp"],
                    nr_neighbours=dictionary["nr_neighbours"],
                    nr_interfaces=dictionary["nr_interfaces"],
                    nr_jumps=dictionary["nr_jumps"])

        if "neighbours" in dictionary:
            message.neighbours = dictionary["neighbours"]
            message.interfaces = dictionary["interfaces"]
        
        elif "jumps" in dictionary:
            message.jumps = dictionary["jumps"]
        
        return message
    