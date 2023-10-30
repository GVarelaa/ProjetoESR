import json
import sys
import socket
import threading
from message import Message

class Server:
    def __init__(self, server_type, database, bootstrapper_addr=None, file=None):
        self.server_type = server_type
        self.database = database
        self.neighbours = list()
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.bind(("", 7777))
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket.bind(("", 7778))

        if self.server_type == 0:
            with open(file) as f:
                self.nodes = json.load(f)
        
        else:
            addr_list = bootstrapper_addr.split(":")
            self.bootstrapper_addr = (addr_list[0], int(addr_list[1]))

    def request_neighbours(self):
        self.control_socket.sendto(Message(0, [], "").serialize(), self.bootstrapper_addr)
        msg_received, addr = self.control_socket.recvfrom(1024)
        decoded_msg = Message.deserialize(msg_received)

        if decoded_msg.type == 1:
            self.neighbours = decoded_msg.data

        print(self.neighbours)

    def neighbours_worker(self, addr):
        for key, value in self.nodes.items():
            if addr[0] in value["interfaces"]: # é esse o servidor
                msg = Message(1, [], value["neighbours"])
                self.control_socket.sendto(msg.serialize(), addr)
    
    def control_service(self):
        try:
            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                decoded_msg = Message.deserialize(msg)

                if self.server_type == 0 and decoded_msg.type == 0:
                    threading.Thread(target=self.neighbours_worker, args=(addr,)).start()
            
        finally:
            self.control_socket.close()
