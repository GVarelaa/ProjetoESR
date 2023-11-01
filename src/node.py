import json
import sys
import socket
import threading
from message import Message
from datetime import datetime

class Node:
    def __init__(self, ntype, bootstrapper_addr=None, file=None):
        self.type = ntype
        self.tree = dict()
        self.interfaces = list()
        self.neighbours = list()
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.bind(("", 7777))
        self.data_socket.bind(("", 7778))

        if self.type == 0:
            with open(file) as f:
                self.nodes = json.load(f)
        else:
            addr_list = bootstrapper_addr.split(":")
            self.bootstrapper_addr = (addr_list[0], int(addr_list[1]))


    def request_neighbours(self):
        self.control_socket.sendto(Message(0).serialize(), self.bootstrapper_addr)

        msg, addr = self.control_socket.recvfrom(1024)
        decoded_msg = Message.deserialize(msg)

        if decoded_msg.type == 1:
            self.neighbours = decoded_msg.data["neighbours"]
            self.interfaces = decoded_msg.data["interfaces"]


    def neighbours_worker(self, addr):
        for key, value in self.nodes.items():
            if addr[0] in value["interfaces"]: # é esse o servidor
                msg = Message(1, data=value)
                self.control_socket.sendto(msg.serialize(), addr)
            

    def subscription_worker(self, addr, msg):
        if self.node.type != 2:
            for ind, neighbour in enumerate(self.neighbours):
                if neighbour != addr[0]:
                    msg = msg.jumps.append(self.interfaces[ind])
                    self.control_socket.sendto(msg.serialize(), (neighbour, 7777))
        else: # RP Node
            timestamp = datetime.timestamp(datetime.now())
            initial_timestamp = datetime.strptime(msg.timestamp, '%Y-%m-%d %H:%M:%S')
            time_differences_s = timestamp.seconds - initial_timestamp.seconds
            time_differences_ms = time_differences_s * 1000

            if msg.jumps[0] in self.tree:
                latency, neighbour = self.tree[msg.jumps[0]]

                if time_differences_ms < latency:
                    self.tree[msg.jumps[0]] = (time_differences_ms, msg.jumps[-1])
            else:
                self.tree[msg.jumps[0]] = (time_differences_ms, msg.jumps[-1])

    
    def control_service(self):
        # Nó folha
        if len(self.neighbours) == 1:
            timestamp = datetime.timestamp(datetime.now())
            self.control_socket.sendoto(Message(2, timestamp=timestamp).serialize(), (self.neighbours[0], 7777))

        try:
            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                decoded_msg = Message.deserialize(msg)

                if self.type == 0 and decoded_msg.type == 0:
                    threading.Thread(target=self.neighbours_worker, args=(addr,)).start()
                
                elif decoded_msg.type == 2:
                    threading.Thread(target=self.subscription_worker, args=(addr,decoded_msg,)).start()
            
        finally:
            self.control_socket.close()
