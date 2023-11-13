import sys
import socket
import threading
import traceback
import logging
import argparse
import time
from datetime import datetime
from random import randint
from utils.videostream import VideoStream
from packets.rtp_packet import RtpPacket
from packets.control_packet import ControlPacket

class Server:
    def __init__(self, filenames):
        self.videostreams = dict()
        for file in filenames:
            self.videostreams[file] = VideoStream("../videos/"+file)
            
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.bind(('', 7777))
        self.event = threading.Event()
        #self.worker = threading.Thread(target=self.send_rtp).start()

        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.info(f"Streaming service listening on port {self.control_socket.getsockname()[1]}")


    def control_worker(self, addr, msg):
        """Process RTSP request sent from the client."""
        # Get the media file name
        #filename = line1[1]
        
        # Get the RTSP sequence number 
        #seq = request[1].split(' ')
        
        if msg.type == ControlPacket.PLAY and msg.response == 1:
            filename = msg.contents[0]

            if filename in self.videostreams:
                print("entrei")
                # Confirmação : adicionar response code = 1
                self.control_socket.sendto(msg.serialize(), addr) # O ficheiro não está nas streams

                send_stream_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                
                #self.control_socket.sendto(msg.serialize(), addr) # É uma response a dizer que recebeu direito, adicionar response
                
                # Create a new thread and start sending RTP packets
                #self.event = threading.Event()
                threading.Thread(target=self.send_rtp, args=(addr, send_stream_socket, filename)).start()
            else:
                msg.error = 1
                self.control_socket.sendto(msg.serialize(), addr) # O ficheiro não está nas streams
        
        elif msg.type == ControlPacket.STATUS and msg.response == 0:
            actual_timestamp = float(datetime.now().timestamp())
            
            msg = ControlPacket(ControlPacket.STATUS, response=1, latency=actual_timestamp, contents=list(self.videostreams.keys()))
            self.control_socket.sendto(msg.serialize(), addr)

            self.logger.info(f"Control Service: Metrics sent to {addr[0]}")
            self.logger.debug(f"Message sent: {msg}")


        # Process SETUP request
        """
        if msg.type == self.JOIN:
            if self.state == self.INIT:
                # Update state
                print("processing SETUP\n")
                
                try:
                    self.clientInfo['videoStream'] = VideoStream(filename)
                    self.state = self.READY
                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
                
                # Generate a randomized RTSP session ID
                self.clientInfo['session'] = randint(100000, 999999)
                
                # Send RTSP reply
                self.replyRtsp(self.OK_200, seq[1])
                
                # Get the RTP/UDP port from the last line
                self.clientInfo['rtpPort'] = request[2].split(' ')[3]
        
        # Process PLAY request 		
        elif requestType == self.PLAY:
            if self.state == self.READY:
                print("processing PLAY\n")
                self.state = self.PLAYING
                
                # Create a new socket for RTP/UDP
                self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                
                self.replyRtsp(self.OK_200, seq[1])
                
                # Create a new thread and start sending RTP packets
                self.clientInfo['event'] = threading.Event()
                self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
                self.clientInfo['worker'].start()
        
        # Process PAUSE request
        elif requestType == self.PAUSE:
            if self.state == self.PLAYING:
                print("processing PAUSE\n")
                self.state = self.READY
                
                self.clientInfo['event'].set()
            
                self.replyRtsp(self.OK_200, seq[1])
        
        # Process TEARDOWN request
        elif requestType == self.TEARDOWN:
            print("processing TEARDOWN\n")

            self.clientInfo['event'].set()
            
            self.replyRtsp(self.OK_200, seq[1])
            
            # Close the RTP socket
            self.clientInfo['rtpSocket'].close()
        """

    def control_service(self):
        try:
            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                msg = ControlPacket.deserialize(msg)

                self.logger.info(f"Control Service: Message received from {addr[0]}")
                self.logger.debug(f"Message received: {msg}")
                
                threading.Thread(target=self.control_worker, args=(addr, msg,)).start()

        finally:
            self.control_socket.close()


    def send_rtp(self, addr, send_stream_socket, filename):
        """Send RTP packets over UDP."""
        while True:
            self.event.wait(0.05)
            
            # Stop sending if request is PAUSE or TEARDOWN
            #if self.event.isSet():
            #    break
                
            data = self.videostreams[filename].get_next_frame()
            
            if data:
                frame_nr = self.videostreams[filename].get_frame_nr()
                try:
                    packet =  self.make_rtp(data, frame_nr)
                    send_stream_socket.sendto(packet, (addr[0], 7778))

                    self.logger.debug(f"Streaming Service: RTP Packet {frame_nr} sent to {addr[0]}")
                except:
                    print("Connection Error")
                    print('-'*60)
                    traceback.print_exc(file=sys.stdout)
                    print('-'*60)
            else:
                self.logger.debug(f"Streaming Service: All RTP Packet were sent to {addr[0]}")
                break #Podemos fazer isto?


    def make_rtp(self, payload, frame_nr):
        """RTP-packetize the video data."""
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26 # MJPEG type

        seqnum = frame_nr
        ssrc = 0
        
        rtpPacket = RtpPacket()
        
        rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
        
        return rtpPacket.get_packet()


def list_of_strings(arg):
    return arg.split(" ")   


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-videostreams", help="filenames", type=list_of_strings)
    args = parser.parse_args()

    server = Server(args.videostreams)
    server.control_service()


if __name__ == "__main__":
    main()