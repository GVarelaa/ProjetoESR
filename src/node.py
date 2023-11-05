import json
import time
import socket
import threading
import logging
import copy
from message import Message
from datetime import datetime
from database import Database

class Node:
    def __init__(self, ntype, bootstrapper_addr=None, file=None):
        self.type = ntype

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.subscription_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.control_socket.bind(("", 7777))
        self.subscription_socket.bind(("", 7779))
        self.data_socket.bind(("", 7778))

        if self.type == 0:
            with open(file) as f:
                self.nodes = json.load(f)
        else:
            addr_list = bootstrapper_addr.split(":")
            self.bootstrapper_addr = (addr_list[0], int(addr_list[1]))
        
        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.database = Database(self.logger)


    def request_neighbours(self):
        self.control_socket.settimeout(5)
        retries = 3
        wait_time = 2
        received = False

        while not received and retries > 0:
            if retries != 3:
                wait_time *= 2
                time.sleep(wait_time)
                    
            self.control_socket.sendto(Message(0).serialize(), self.bootstrapper_addr)
            self.logger.info("Control Service: Asked for neighbours")

            try:
                msg, _ = self.control_socket.recvfrom(1024)
                received = True
                decoded_msg = Message.deserialize(msg)

                if decoded_msg.type == 1:
                    self.database.neighbours = decoded_msg.neighbours

                    self.logger.info("Control Service: Neighbours received")
                    self.logger.debug(f"Neighbours: {self.database.neighbours}")
            
            except socket.timeout:
                retries -= 1

                if retries > 0:
                    self.logger.info(f"Control Service: Could not receive response to neighbours request")

        if not received:
            self.logger.info("Control Service: Could not receive response to neighbours request after 3 retries")
            exit() # É este o comportamento que queremos ?


    def neighbours_worker(self, addr):
        for key, value in self.nodes.items():
            if addr[0] in value["interfaces"]: # é esse o servidor
                msg = Message(1, neighbours=value["neighbours"])
                self.control_socket.sendto(msg.serialize(), addr)

                self.logger.info(f"Control Service: Neighbours sent to {addr[0]}")
                self.logger.debug(f"Neighbours: {msg}")
            

    def subscription_worker(self, addr, msg):
        # Enviar ack para trás
        ack_msg = copy.deepcopy(msg)
        ack_msg.flag = 1
        self.control_socket.sendto(ack_msg.serialize(), addr)
        self.logger.info(f"Control Service: Acknowledgment message sent to {addr[0]}")
        self.logger.debug(f"Ack message sent: {msg}")
        
        if msg.jumps is None:
            msg.jumps = list()
        msg.jumps.append(addr[0])

        self.database.insert(msg.jumps[0], addr[0], msg.timestamp)

        if self.type != 2:
            some_received = False # Se recebeu de algum dos neighbours

            for neighbour in self.database.neighbours:
                if neighbour != addr[0]: # Se o vizinho não for o que enviou a mensagem
                    self.control_socket.settimeout(5)
                    retries = 3
                    wait_time = 2
                    received = False

                    while not received and retries > 0:
                        if retries != 3:
                            wait_time *= 2
                            time.sleep(wait_time)
                                
                        self.control_socket.sendto(msg.serialize(), (neighbour, 7777))
                        self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                        self.logger.debug(f"Message sent: {msg}")

                        try:
                            msg, _ = self.subscription_socket.recvfrom(1024)
                            decoded_msg = Message.deserialize(msg)

                            if decoded_msg.flag == 1:
                                received = True
                                some_received = True
                                self.logger.info("Control Service: Acknowledgment received")
                        
                        except socket.timeout:
                            retries -= 1

                            if retries > 0:
                                self.logger.info(f"Control Service: Could not receive an acknowledgment from subscription request")

                    if not received:
                        self.logger.info("Control Service: Could not receive an acknowledgment from subscription request after 3 retries")
            
            if not some_received:
                msg.jumps.pop()
                next_step = msg.jumps.pop()
                self.control_socket.sendto(Message(2, flag=2, jumps=msg.jumps).serialize(), (next_step,7777))
                self.logger.info(f"Control Service: Could not forward subscription message from {msg.jumps[0]}. Sending back to {msg.jumps[-1]}")
    

    def sendback_worker(self, addr, msg):
        if len(self.database.neighbours != 1):
            next_step = msg.jumps.pop()
            self.control_socket.sendto(Message(2, flag=2, jumps=msg.jumps).serialize(), (next_step,7777))
            self.logger.info(f"Control Service: Could not forward subscription message from {msg.jumps[0]}. Sending back to {msg.jumps[-1]}")
        else:
            exit()


    def leave_worker(self, msg):
        self.database.remove(msg.jumps[0])
    

    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                decoded_msg = Message.deserialize(msg)

                self.logger.info(f"Control Service: Subscription message received from neighbour {addr[0]}")
                self.logger.debug(f"Message received: {decoded_msg}")

                if self.type == 0 and decoded_msg.type == 0:
                    threading.Thread(target=self.neighbours_worker, args=(addr,)).start()
                
                elif decoded_msg.type == 2:
                    if decoded_msg.flag == 0:
                        threading.Thread(target=self.subscription_worker, args=(addr, decoded_msg,)).start()
                    
                    elif decoded_msg.flag == 2:
                        threading.Thread(target=self.sendback_worker, args=(addr, decoded_msg,)).start()
                
                elif decoded_msg.type == 3 and decoded_msg.flag != 1:
                    threading.Thread(target=self.leave_worker, args=(decoded_msg,)).start()
            
        finally:
            self.control_socket.close()

    
    def subscription_service(self):
        try:
            wait = 10 # 10 segundos
            
            while True:
                self.subscription_socket.settimeout(5)
                retries = 3
                wait_time = 2
                received = False

                while not received and retries > 0:
                    if retries != 3:
                        wait_time *= 2
                        time.sleep(wait_time)
                            
                    msg = Message(2, timestamp=float(datetime.now().timestamp()))
                    self.subscription_socket.sendto(msg.serialize(), (self.database.neighbours[0], 7777))

                    self.logger.info(f"Subscription Service: Subscription message sent to neighbour {self.database.neighbours[0]}")
                    self.logger.debug(f"Message sent: {msg}") 

                    try:
                        msg, _ = self.subscription_socket.recvfrom(1024)
                        decoded_msg = Message.deserialize(msg)

                        if decoded_msg.flag == 1:
                            received = True
                            self.logger.info("Subscription Service: Acknowledgment received")
                    
                    except socket.timeout:
                        retries -= 1

                        if retries > 0:
                            self.logger.info(f"Subscription Service: Could not receive an acknowledgment from subscription request")

                if not received:
                    self.logger.info("Subscription Service: Could not receive an acknowledgment from subscription request after 3 retries")
                    exit() # É este o comportamento que queremos ?

                else:
                    time.sleep(wait)
        
        finally:
            self.subscription_socket.close()

    
    def pruning_service(self):
        wait = 20 # 20 segundos
        while True:
            timestamp = float(datetime.now().timestamp())
            
            self.database.prune(timestamp, wait)

            time.sleep(wait)

