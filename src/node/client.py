from node import *

class Client(Node):
    def __init__(self, bootstrapper):
        super.__init__(bootstrapper=bootstrapper)

        self.polling_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.polling_socket.bind(("", 7779))

    
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


    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                msg = Message.deserialize(msg)

                self.logger.info(f"Control Service: Subscription message received from neighbour {addr[0]}")
                self.logger.debug(f"Message received: {msg}")
                
                # Completar - receber erros de subscrição ?
            
        finally:
            self.control_socket.close()