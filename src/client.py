from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
from rtppacket import RtpPacket
from message import Message

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
    JOIN = 4
    PLAY = 5
    PAUSE = 6
    LEAVE = 7
    STREAM_REQ = 8

    def __init__(self, master, addr, port):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.create_widgets()
        self.addr = addr
        self.port = int(port)
        self.rtsp_seq = 0
        self.session_id = 0
        self.request_sent = -1
        self.teardown_acked = 0
        self.open_rtp_port()
        self.play_movie()
        self.frame_nr = 0


    def create_widgets(self):
        """Build GUI."""
        # Create Setup button
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setup_movie
        self.setup.grid(row=1, column=0, padx=2, pady=2)
        
        # Create Play button		
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.play_movie
        self.start.grid(row=1, column=1, padx=2, pady=2)
        
        # Create Pause button			
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pause_movie
        self.pause.grid(row=1, column=2, padx=2, pady=2)
        
        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] =  self.exit_client
        self.teardown.grid(row=1, column=3, padx=2, pady=2)
        
        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 


    def setup_movie(self):
        """Setup button handler."""
        print("Not implemented...")


    def exit_client(self):
        """Teardown button handler."""
        self.master.destroy() # Close the gui window
        os.remove(CACHE_FILE_NAME + str(self.session_id) + CACHE_FILE_EXT) # Delete the cache image from video


    def pause_movie(self):
        """Pause button handler."""
        print("Not implemented...")


    def play_movie(self):
        """Play button handler."""
        # Create a new thread to listen for RTP packets
        server_ip = ""
        rtsp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rtsp_socket.sendto(Message(self.STREAM_REQ, contents=["movie.Mjpeg"]).serialize(), ("10.0.6.10", 7777))

        #msg, _ = rtsp_socket.recvfrom(2048)

        #msg = Message.deserialize(msg)

        #if msg.msg_type == 8:
        threading.Thread(target=self.listen_rtp).start()
        self.play_event = threading.Event()
        self.play_event.clear()


    def listen_rtp(self):		
        """Listen for RTP packets."""
        while True:
            try:
                data = self.rtp_socket.recv(20480)
                if data:
                    rtp_packet = RtpPacket()
                    rtp_packet.decode(data)
                    
                    curr_frame_nr = rtp_packet.get_seq_num()
                    print("Current Seq Num: " + str(curr_frame_nr))
                                        
                    if curr_frame_nr > self.frame_nr: # Discard the late packet
                        self.frame_nr = curr_frame_nr
                        self.update_movie(self.write_frame(rtp_packet.get_payload()))
            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.play_event.isSet(): 
                    break
                
                self.rtp_socket.shutdown(socket.SHUT_RDWR)
                self.rtp_Socket.close()
                break
                
    
    def write_frame(self, data):
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + str(self.session_id) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()
        
        return cachename


    def update_movie(self, image_file):
        """Update the image file as video frame in the GUI."""
        photo = ImageTk.PhotoImage(Image.open(image_file))
        self.label.configure(image = photo, height=288) 
        self.label.image = photo
        
    
    def open_rtp_port(self):
        """Open RTP socket binded to a specified port."""
        # Create a new datagram socket to receive RTP packets from the server
        self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set the timeout value of the socket to 0.5sec
        #self.rtp_socket.settimeout(5)
        
        try:
            # Bind the socket to the address using the RTP port
            self.rtp_socket.bind(("", self.port))
            print('\nBind \n')
        except:
            tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtp_port)


    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pause_movie()
        if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exit_client()
        else: # When the user presses cancel, resume playing.
            self.play_movie()


def main():
    addr = '127.0.0.1'
    port = 7778
    root = Tk()
    # Create a new client
    app = Client(root, addr, port)
    app.master.title("Cliente Exemplo")	
    root.mainloop()


if __name__ == "__main__":
    main()

"""
import threading
import socket
import time
from datetime import datetime
from .node import Node
from message import Message
from exceptions import *

class Client(Node):
    def __init__(self, bootstrapper):
        super().__init__(bootstrapper=bootstrapper)

        self.polling_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.polling_socket.bind(("", 7779))

    
    def polling_service(self):
        try:
            wait = 100 # 100 segundos
            
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
"""
