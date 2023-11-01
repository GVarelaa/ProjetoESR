import json
import sys
import socket
import threading
from message import Message

class Server:
    def __init__(self, server_type, database, bootstrapper_addr=None, file=None):
        self.server_type = server_type
        self.database = database
        self.interfaces = list()
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
        self.control_socket.sendto(Message(0, [], [], "").serialize(), self.bootstrapper_addr)
        msg_received, addr = self.control_socket.recvfrom(1024)
        decoded_msg = Message.deserialize(msg_received)

        if decoded_msg.type == 1:
            self.neighbours = decoded_msg.data["neighbours"]
            self.interfaces = decoded_msg.data["interfaces"]

    def neighbours_worker(self, addr):
        for key, value in self.nodes.items():
            if addr[0] in value["interfaces"]: # é esse o servidor
                msg = Message(1, [], [], value)
                self.control_socket.sendto(msg.serialize(), addr)
            
    def subscription_worker(self, addr, msg):
        if server.type != 2:
            for ind, neighbour in enumerate(self.neighbours):
                if neighbour != addr[0]:
                    self.control_socket.sendto(Message(2, [], jumps.append(self.interfaces[ind]), "").serialize(), (neighbour, 7777))
        else:
            print(msg.jumps)
    
    def control_service(self):
        if len(self.neighbours) == 1:
            self.control_socket.sendoto(Message(2, [], [], "").serialize(), (self.neighbours[0], 7777))

        try:
            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                decoded_msg = Message.deserialize(msg)

                if self.server_type == 0 and decoded_msg.type == 0:
                    threading.Thread(target=self.neighbours_worker, args=(addr,)).start()
                
                elif decoded_msg.type == 2:
                    threading.Thread(target=self.subscription_worker, args=(addr,decoded_msg,)).start()
            
        finally:
            self.control_socket.close()
