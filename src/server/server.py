import sys
import socket
import threading
import traceback
import logging
from random import randint
from VideoStream import VideoStream
from RtpPacket import RtpPacket
from message import Message

class Server:
    JOIN = 4
    PLAY = 5
    PAUSE = 6
    LEAVE = 7
    STREAM_REQ = 8

    def __init__(self, filenames):
        self.videostreams = dict()
        for file in filenames:
            self.videostreams[file] = VideoStream(file)
            
        self.rtp_addr = (socket.gethostbyname('127.0.0.1'), 250000)
        self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.event = threading.Event()
        #self.worker = threading.Thread(target=self.send_rtp).start()

        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.info("Streaming service listening on port 25000")


    def server_worker(self, addr, msg):
        """Process RTSP request sent from the client."""
		# Get the media file name
		filename = line1[1]
		
		# Get the RTSP sequence number 
		seq = request[1].split(' ')
		
        if msg.type == self.STREAM_REQ:
            filename = msg.contents[0]

            if filename in self.videostreams:
				send_stream_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
                rtp_socket.sendto(msg.serialize(), addr) # É uma response a dizer que recebeu direito, adicionar response
				
				# Create a new thread and start sending RTP packets
				#self.event = threading.Event()
				threading.Thread(target=self.send_rtp, args=(send_stream_socket, filename)).start()
            else:
                msg.error = 1
                rtp_socket.sendto(msg.serialize(), addr) # O ficheiro não está nas streams


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

    def control_service(self, ):
        try:
            while True:
                msg, addr = self.rtp_socket.recvfrom(1024)
                msg = Message.deserialize(msg)

                self.logger.info(f"Control Service: Message received from {addr[0]}")
                self.logger.debug(f"Message received: {msg}")
                
                threading.Thread(target=self.server_worker, args=(addr, msg,)).start()

        finally:
            self.rtp_socket.close()


    def send_rtp(self, send_stream_socket, filename):
        """Send RTP packets over UDP."""
        while True:
            #self.event.wait(0.05)
            
            # Stop sending if request is PAUSE or TEARDOWN
            #if self.event.isSet():
            #    break
                
            data = self.videostreams[filename].get_next_frame()
            if data:
                frame_nr = self.clientInfo['videoStream'].get_frame_nr()
                try:
                    packet =  self.make_rtp(data, frame_nr)
                    self.rtp_socket.sendto(packet, self.rtp_addr)
                except:
                    print("Connection Error")
                    print('-'*60)
                    traceback.print_exc(file=sys.stdout)
                    print('-'*60)
        # Close the RTP socket
        self.clientInfo['rtpSocket'].close()
        print("All done!")


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
        print("Encoding RTP Packet: " + str(seqnum))
        
        return rtpPacket.getPacket()


def list_of_strings(arg):
    return arg.split(" ")   


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-videostreams", help="filenames", type=list_of_strings)
    args = parser.parse_args()

    Server(args.videostreams)


if __name__ == "__main__":
    main()