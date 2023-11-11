class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		
		self.frame_nr = 0
		

	def get_next_frame(self):
		"""Get next frame."""
		data = self.file.read(5) # Get the framelength from the first 5 bits
		
		if data: 
			frame_length = int(data)
							
			# Read the current frame
			data = self.file.read(frame_length)
			self.frame_nr += 1
		
		return data
	
		
	def get_frame_nr(self):
		"""Get frame number."""
		return self.frame_nr