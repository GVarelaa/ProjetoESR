import json
import socket
from node import *

class Bootstrapper(Node):
    def __init__(self, file):
        super().__init__()

        with open(file) as f:
            self.nodes = json.load(f)


    def neighbours_worker(self, addr):
        for key, value in self.nodes.items():
            if addr[0] in value["interfaces"]: # é esse o servidor
                msg = Message(1, data=value["neighbours"])
                self.control_socket.sendto(msg.serialize(), addr)

                self.logger.info(f"Control Service: Neighbours sent to {addr[0]}")
                self.logger.debug(f"Neighbours: {msg}")


    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                msg = Message.deserialize(msg)

                self.logger.info(f"Control Service: Subscription message received from neighbour {addr[0]}")
                self.logger.debug(f"Message received: {msg}")

                if msg.type == 0:
                    threading.Thread(target=self.neighbours_worker, args=(addr,)).start()
                
                elif msg.type == 2:
                    if msg.flag == 0:
                        threading.Thread(target=self.subscription_worker, args=(addr, msg,)).start()
                    
                    elif msg.flag == 2:
                        threading.Thread(target=self.sendback_worker, args=(addr, msg,)).start()
                
                elif msg.type == 3 and msg.flag != 1:
                    threading.Thread(target=self.leave_worker, args=(msg,)).start()
            
        finally:
            self.control_socket.close()


    def request_neighbours(self):
        my_ip = self.control_socket.gethostbyname(socket.gethostname())

        for key, value in self.nodes.items():
            if my_ip in value["interfaces"]: # é esse o servidor
                self.database.neighbours = value["neighbours"]

