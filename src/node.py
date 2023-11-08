import json
import time
import socket
import threading
import logging
import copy
from message import Message
from datetime import datetime
from database import Database
from exceptions import *

class Node:
    def __init__(self, ntype, bootstrapper_addr=None, file=None):
        self.type = ntype

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.polling_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.control_socket.bind(("", 7777))
        self.polling_socket.bind(("", 7779))
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


    def send_udp(self, msg, retries, timeout, service, address, socket_udp):
        received = False
        socket_udp.settimeout(timeout)

        while not received and retries > 0:
            if retries != 3:
                self.logger.info(f"{service}: New attempt sent to neighbour {address[0]}")

            socket_udp.sendto(msg.serialize(), address)

            try:
                msg, _ = socket_udp.recvfrom(1024)
                msg = Message.deserialize(msg)

                received = True
            
            except socket.timeout:
                if retries > 0:
                    self.logger.info(f"{service}: Could not receive a response from {address[0]}")

                retries -= 1
                socket_udp.settimeout(socket_udp.gettimeout()*2)  

        if received == True:
            return msg
        else:
            raise ACKFailed("Could not receive a response")
        

    def request_neighbours(self):
        message = Message(0)

        self.logger.info("Control Service: Asked for neighbours")
        try:
            response = self.send_udp(message, 3, 2, "Control Service", self.bootstrapper_addr, self.control_socket)

            if response.type == 1:
                self.database.neighbours = response.data

                self.logger.info("Control Service: Neighbours received")
                self.logger.debug(f"Neighbours: {self.database.neighbours}")

        except ACKFailed:
            self.logger.info("Control Service: Could not receive response to neighbours request after 3 retries")
            exit() # É este o comportamento que queremos ?



    def neighbours_worker(self, addr):
        for key, value in self.nodes.items():
            if addr[0] in value["interfaces"]: # é esse o servidor
                msg = Message(1, data=value["neighbours"])
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

        if msg.data is None:
            msg.data = list()
        msg.data.append(addr[0])

        self.database.insert(msg.data[0], addr[0], msg.timestamp)

        if self.type != 2:
            # Criar novo socket
            forward_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # some_received = False # Se recebeu de algum dos neighbours

            for neighbour in self.database.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
                if neighbour != addr[0]: # Se o vizinho não for o que enviou a mensagem
                    try:
                        self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                        self.logger.debug(f"Message sent: {msg}")
                        
                        response = self.send_udp(msg, 3, 2, "Control Service", (neighbour, 7777), forward_socket)

                        if response.flag == 1:
                            # some_received = True
                            self.logger.info("Control Service: Acknowledgment received")

                    except ACKFailed:
                        self.logger.info("Control Service: Could not receive an acknowledgment from subscription request after 3 retries")
            
            forward_socket.close()
            
            #if not some_received:
            #    msg.data.pop()
            #    next_step = msg.data.pop()#
            #    self.control_socket.sendto(Message(2, flag=2, data=msg.data).serialize(), (next_step, 7777))
            #    self.logger.info(f"Control Service: Could not forward subscription message from {msg.data[0]}. Sending back to {msg.data[-1]}")
    

    def sendback_worker(self, addr, msg):
        if len(self.database.neighbours != 1):
            next_step = msg.data.pop()
            self.control_socket.sendto(Message(2, flag=2, data=msg.data).serialize(), (next_step, 7777))
            self.logger.info(f"Control Service: Could not forward subscription message from {msg.data[0]}. Sending back to {msg.data[-1]}")
        else:
            exit()


    def leave_worker(self, msg):
        self.database.remove(msg.data[0])
    

    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                msg = Message.deserialize(msg)

                self.logger.info(f"Control Service: Subscription message received from neighbour {addr[0]}")
                self.logger.debug(f"Message received: {msg}")

                if self.type == 0 and msg.type == 0:
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

    
    def polling_service(self):
        try:
            wait = 30 # 10 segundos
            
            while True:
                msg = Message(2, timestamp=float(datetime.now().timestamp()))

                try:
                    self.logger.info(f"Subscription Service: Subscription message sent to neighbour {self.database.neighbours[0]}")
                    self.logger.debug(f"Message sent: {msg}") 

                    response = self.send_udp(msg, 3, 2, "Subscription Service", (self.database.neighbours[0], 7777), self.polling_socket)

                    if response.flag == 1: 
                        self.logger.info("Subscription Service: Acknowledgment received")

                    time.sleep(wait)
                except ACKFailed:
                    self.logger.info("Subscription Service: Could not receive an acknowledgment from subscription request after 3 retries")
                    exit() # É este o comportamento que queremos ?
        
        finally:
            self.polling_socket.close()

    
    def pruning_service(self):
        wait = 20 # 20 segundos
        while True:
            timestamp = float(datetime.now().timestamp())
            
            self.database.prune(timestamp, wait)

            time.sleep(wait)

