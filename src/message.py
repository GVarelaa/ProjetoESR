import pickle
import io
from datetime import datetime

class Message:
    def __init__(self, msg_type, flag=0, timestamp=0, data=None):
        # Header
        self.type = msg_type
        self.flag = flag
        self.timestamp = timestamp
        # Data
        self.data = data
    
    def __str__(self):
        return f"Type: {self.type} | Flag: {self.flag} | Timestamp: {self.timestamp} | Data: {self.data}"

    def __repr__(self):
        return f"Type: {self.type} | Flag: {self.flag} | Timestamp: {self.timestamp} | Data: {self.data}"

    def serialize(self):
        # Header
        dictionary = { 
            "type": self.type,
            "flag": self.flag,
            "timestamp": self.timestamp
        }

        # Data
        if self.data is not None:
            dictionary["data"] = self.data

        return pickle.dumps(dictionary)

    @staticmethod
    def deserialize(bytes):
        dictionary = pickle.loads(bytes)

        message = Message(dictionary["type"], flag=dictionary["flag"], timestamp=dictionary["timestamp"])

        if "data" in dictionary:
            message.data = dictionary["data"]
        
        return message
    