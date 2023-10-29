import pickle

class Message:
    def __init__(self, msg_type, flags, data):
        self.type = msg_type
        self.flags = flags
        self.data = data
    
    def __str__(self):
        return f"type: {self.type}, data: {self.data}"

    def __repr__(self):
        return f"type: {self.type}, data: {self.data}"

    def serialize(self):
        # type - 1 byte
        type_bytes = self.type.to_bytes(1, 'big')
        
        data_bytes = pickle.dumps(self.data)

        return type_bytes + data_bytes

    @staticmethod
    def deserialize(bytes):
        data = pickle.loads(bytes[1:])

        return Message(int(bytes[0]), [], data)
    