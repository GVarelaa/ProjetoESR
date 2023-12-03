import argparse
import socket
import threading
import logging
import time
import random
import os
import errno
from datetime import datetime
from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
from packets.control_packet import ControlPacket
from packets.rtp_packet import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
    def __init__(self, master, bootstrapper, videofile, debug_mode=False):
        self.master = master
        self.videofile = videofile
        self.neighbour = None

        address = bootstrapper.split(":")
        self.bootstrapper = (address[0], int(address[1]))

        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.create_widgets()

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.bind(("", 7777))

        if debug_mode:
            logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        else:
            logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.setup() # Request neighbours

        threading.Thread(target=self.control_service, args=()).start()
        #threading.Thread(target=self.polling_service, args=()).start()
        
        self.rtsp_seq = 0
        self.session_id = random.randint(1,100)
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
        
        # Create Stop button			
        self.stop = Button(self.master, width=20, padx=3, pady=3)
        self.stop["text"] = "Stop"
        self.stop["command"] = self.stop_movie
        self.stop.grid(row=1, column=2, padx=2, pady=2)
        
        # Create Exit button
        self.exit = Button(self.master, width=20, padx=3, pady=3)
        self.exit["text"] = "Exit"
        self.exit["command"] =  self.exit_client
        self.exit.grid(row=1, column=3, padx=2, pady=2)
        
        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 


    def setup(self):
        self.control_socket.sendto(ControlPacket(ControlPacket.NEIGHBOURS).serialize(), self.bootstrapper)
        self.logger.info("Setup: Asked for neighbours")

        try:
            self.control_socket.settimeout(5) # 5 segundos? perguntar ao lost

            data, _ = self.control_socket.recvfrom(1024)
            msg = ControlPacket.deserialize(data)

            if msg.type == ControlPacket.NEIGHBOURS and msg.response == 1:
                self.neighbour = msg.neighbours[0]
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
        msg = ControlPacket(ControlPacket.PLAY, contents=[self.videofile])
        self.control_socket.sendto(msg.serialize(), (self.neighbour, 7777))

        self.logger.debug(f"Message sent: {msg}")
    

    def stop_movie(self):
        """Stop button handler."""
        msg = ControlPacket(ControlPacket.LEAVE, contents=[self.videofile])
        self.control_socket.sendto(msg.serialize(), (self.neighbour, 7777))
        

    def exit_client(self):
        """Exit button handler."""
        msg = ControlPacket(ControlPacket.LEAVE, contents=[self.videofile])
        self.control_socket.sendto(msg.serialize(), (self.neighbour, 7777))
        
        self.logger.debug(f"Message sent: {msg}")

        self.master.destroy() # Close the gui window
        os.remove(CACHE_FILE_NAME + str(self.session_id) + CACHE_FILE_EXT) # Delete the cache image from 
        
        # FALTA FECHAR AQUI O CLIENTE E FECHAR SOCKET DE DATA


    def listen_rtp(self, port):		
        """Listen for RTP packets."""

        self.logger.info(f"Streaming Service: Receiving RTP packets")        
        
        try:
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            data_socket.bind(("", port))
        
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:
                pass
        
        while True:
            try:
                data, addr = data_socket.recvfrom(20480)
                if data:
                    rtp_packet = RtpPacket()
                    rtp_packet.decode(data)
                    
                    curr_frame_nr = rtp_packet.get_seq_num()
                    self.logger.debug(f"Streaming Service: RTP Packet {curr_frame_nr} received from {addr[0]}")

                    if curr_frame_nr > self.frame_nr: # Discard the late packet
                        self.frame_nr = curr_frame_nr
                        self.update_movie(self.write_frame(rtp_packet.get_payload()))
            
            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.play_event.isSet(): 
                    break
                
                data_socket.shutdown(socket.SHUT_RDWR)
                data_socket.close()
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


    def control_worker(self, address, msg):
        if msg.type == ControlPacket.PLAY and msg.response == 1:
            self.logger.info(f"Control Service: Confirmation message received from {address[0]}")
            self.logger.debug(f"Message received: {msg}")

            threading.Thread(target=self.listen_rtp, args=(msg.port,)).start()
            self.play_event = threading.Event()
            self.play_event.clear()
    
        elif msg.type == ControlPacket.MEASURE and msg.response == 0:
            self.logger.info(f"Control Service: Measure request received from neighbour {address[0]}")
            self.logger.debug(f"Message received: {msg}")

            msg.response = 1
            self.control_socket.sendto(msg.serialize(), (address[0], 7777))

        
    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                data, address = self.control_socket.recvfrom(1024)
                message = ControlPacket.deserialize(data)

                threading.Thread(target=self.control_worker, args=(address, message,)).start()

        finally:
            self.control_socket.close()


    def polling_service(self):
        try:
            wait = 5 # MUDAR PARA 0.5S !!!!!!!!!!!!!!!!
            
            while True:
                msg = ControlPacket(ControlPacket.PLAY, contents=[self.videofile])

                self.control_socket.sendto(msg.serialize(), (self.neighbour, 7777))

                self.logger.info(f"Polling Service: Polling message sent to neighbour {self.neighbour}")
                self.logger.debug(f"Message sent: {msg}")
                
                time.sleep(wait)
        
        finally:
            self.control_socket.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-bootstrapper", help="bootstrapper ip")
    parser.add_argument("-videofile", help="filename")
    parser.add_argument("-d", action="store_true", help="activate debug mode")
    args = parser.parse_args()

    debug_mode = False

    if args.d:
        debug_mode = True

    if args.bootstrapper and args.videofile:
        root = Tk()
        app = Client(root, args.bootstrapper, args.videofile, debug_mode=debug_mode)
        app.master.title("Client")	
        root.mainloop()
        
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()