import json
import sys
import socket
import threading
from message import Message

class Bootstrapper:
    def __init__(self, file):
        with open(file) as f:
            self.nodes = json.load(f)

    def neighbours_worker(self, addr, s):
        for key, value in self.nodes.items():
            if addr[0] in value["interfaces"]: # é esse o servidor
                msg = Message(1, [], value["neighbours"])
                s.sendto(msg.serialize(), addr)

    def neighbours_service(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("", 7777))

        try:
            while True:
                msg, addr = s.recvfrom(1024)
                decoded_msg = Message.deserialize(msg)

                if decoded_msg.type == 0:
                    threading.Thread(target=self.neighbours_worker, args=(addr, s)).start()
            
        finally:
            s.close()
            

def main():
    Bootstrapper(sys.argv[1]).neighbours_service()
    

if __name__ == "__main__":
    main()