import argparse
import socket, threading, sys, traceback, os
import logging
import time
from datetime import datetime
from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
from packets.controlpacket import ControlPacket
from packets.rtppacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
    NEIGHBOURS_RESP = 1
    JOIN = 4
    PLAY = 5
    PAUSE = 6
    LEAVE = 7
    STREAM_REQ = 8

    def __init__(self, master, bootstrapper, videofile):
        self.master = master
        self.videofile = videofile
        self.neighbour = None

        address = bootstrapper.split(":")
        self.bootstrapper = (address[0], int(address[1]))

        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.create_widgets()

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.control_socket.bind(("", 7777))
        self.data_socket.bind(("", 7778))

        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.setup() # Request neighbours
        
        self.rtsp_seq = 0
        self.session_id = 0
        self.request_sent = -1
        self.teardown_acked = 0
        self.frame_nr = 0
        self.play_movie()


    def create_widgets(self):
        """Build GUI."""
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


    def setup(self):
        self.control_socket.sendto(ControlPacket(0).serialize(), self.bootstrapper)
        self.logger.info("Setup: Asked for neighbours")

        try:
            self.control_socket.settimeout(5) # 5 segundos? perguntar ao lost

            data, _ = self.control_socket.recvfrom(1024)
            response = ControlPacket.deserialize(data)

            if response.type == self.NEIGHBOURS_RESP:
                self.neighbour = response.neighbours[0]
                self.logger.info("Setup: Neighbours received")
                self.logger.debug(f"Neighbours: {self.neighbour}")
            
            else:
                self.logger.info("Setup: Unexpected response received")
                exit() # É este o comportamento que queremos ?
            
        except socket.timeout:
            self.logger.info("Setup: Could not receive response to neighbours request")
            exit()


    def play_movie(self):
        """Play button handler."""
        control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        msg = ControlPacket(self.JOIN, contents=[self.videofile])
        control_socket.sendto(msg.serialize(), (self.neighbour, 7777))

        self.logger.debug(f"Message sent: {msg}")

        msg = ControlPacket(self.PLAY, contents=[self.videofile])
        control_socket.sendto(msg.serialize(), ("10.0.19.1", 7777))

        self.logger.debug(f"Message sent: {msg}")
        
        threading.Thread(target=self.listen_rtp).start()
        self.play_event = threading.Event()
        self.play_event.clear()


    def exit_client(self):
        """Teardown button handler."""
        self.master.destroy() # Close the gui window
        os.remove(CACHE_FILE_NAME + str(self.session_id) + CACHE_FILE_EXT) # Delete the cache image from video


    def pause_movie(self):
        """Pause button handler."""
        print("Not implemented...")


    def listen_rtp(self):		
        """Listen for RTP packets."""
        while True:
            try:
                data = self.data_socket.recv(20480)
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
                
                self.data_socket.shutdown(socket.SHUT_RDWR)
                self.data_socket.close()
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


    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pause_movie()
        if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exit_client()
        else: # When the user presses cancel, resume playing.
            self.play_movie()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-bootstrapper", help="bootstrapper ip")
    parser.add_argument("-videofile", help="filename")
    args = parser.parse_args()

    if args.bootstrapper and args.videofile:
        root = Tk()
        app = Client(root, args.bootstrapper, args.videofile)
        app.master.title("Client")	
        root.mainloop()
        
    else:
        print("Error: Wrong arguments")
        exit()


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
