import serial
import sys
import crc8
import time

class ert_swc_rm:
	# EnOcean ERT-SWC-RM device base-class.

	# Constants
	## EnOcean configurations
	ENO_TTY = '/dev/ttyEX2'
	ENO_BAUDRATE = 57600

	# EnOcean Communicator Object
	eno_comm = None

	####################################################################################################
	#[Function]: Initiate the ERT-SWC-RM device handler
	#---------------------------------------------------------------------------------------------------
	#[Parameters]:
	#   self {ert_swc_rm} - The ERT-SWC-RM device handler object
	#[Return]: N/A
	####################################################################################################
	def __init__(self):
		self.eno_comm = serial.Serial(self.ENO_TTY, baudrate=self.ENO_BAUDRATE, parity=serial.PARITY_NONE, timeout=1)
		# print("Initiated connection with Enocean Serial Port")

	####################################################################################################
	#[Function]: Finalize the ERT-SWC-RM device handler
	#---------------------------------------------------------------------------------------------------
	#[Parameters]:
	#   self {ert_swc_rm} - The ERT-SWC-RM device handler object
	#[Return]: N/A
	####################################################################################################
	def finalize(self):
		if self.eno_comm != None:
			self.eno_comm.close()
		# print("Closed connection with Enocean Serial Port")

	####################################################################################################
	#[Function]: Send the UTE message to ERT-SWC-RM device to register operation
	#---------------------------------------------------------------------------------------------------
	#[Parameters]:
	#   self {ert_swc_rm} - The ERT-SWC-RM device handler object
	#   devid {str} - The device ID of ERT-SWC-RM device
	#[Return]: N/A
	####################################################################################################
	def write_ute(self, devid):
		# Escape function if EnOcean connection is invalid
		if self.eno_comm == None:
			return False
		## EnOcean data frame offset positions
		HEADER_START_OFFSET = 1
		CRCH_OFFSET = 5
		DATA_START_OFFSET = 6
		DEVICEID_OFFSET = 20
		CRCD_OFFSET = 25
		# Conduct UTE Frame
		out_data = [0x55, 0x00, 0x13, 0x00, 0x0A, 0x29, 0x35, 0x04, 0x00, 0x00, 0x00, 0x00, 0x60, 0x00, 0x31, 0x00, 0x01, 0x02, 0xD1, 0x00, 0xAA, 0xAA, 0xAA, 0xAA, 0x00, 0x6A]
		# Overwrite the Device ID for the ERT-SWC-RM device
		for i in range(4):
			out_data[DEVICEID_OFFSET + i] = devid[i]
		# Calculate the CRC for data part and overwrite into data frame
		out_data[CRCH_OFFSET] = make_crc(out_data[HEADER_START_OFFSET:CRCH_OFFSET])
		out_data[CRCD_OFFSET] = make_crc(out_data[DATA_START_OFFSET:CRCD_OFFSET])
		# Print out log of the full frame of UTE registration message
		cat_data = ''
		for byte in out_data:
			cat_data += ' ' + '{0:0{1}X}'.format(byte, 2)
		print('Sent UTE data frame which is:' + str(cat_data))
		# Write to the serial port of Encean protocol
		self.eno_comm.write(out_data)

####################################################################################################
#[Function]: Calculate CRC checksum for a inputted frame
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   data {str} - The frame of data needed to calculate CRC
#[Return]:
#   hex_result {int|hex formatted} - The calculated CRC result of the input data frame
####################################################################################################
def make_crc(data):
	# Convert input data from int into HEX format
	temp = bytearray()
	for byte in data:
		temp += byte.to_bytes(1, 'big')
	# Calculate and make CRC
	hash = crc8.crc8()
	hash.update(temp)
	result = hash.hexdigest()
	# Convert CRC from string to HEX formatted int
	hex_result = convert_str2hex(result, 1)
	return hex_result[0]

####################################################################################################
#[Function]: Convert a string into Hex formatted data list
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   input_str {str} - Message for converting
#[Return]: N/A
#   out_byte_list {list} - The list of calculated converted data
####################################################################################################
def convert_str2hex(input_str, expected_len=1):
	step = 2
	out_byte_list = []
	# Split HEX formatted ID string into int-type bytes in list
	if len(input_str) == (expected_len * step):
		try:
			for i in range(len(input_str)//2):
				temp = int(input_str[(i*2):(i*2+step)], 16)
				out_byte_list.append(temp)
			return out_byte_list
		except Exception as err:
			print("Failed to convert string to HEX data, error: " + str(err))
	else:
		print("Input string has false length. Please input string with correct lentgh as " + str(expected_len * step))
	# In case failing to convert, return a list sample
	default_mask = 0xAA
	for i in range(expected_len):
		out_byte_list.append(default_mask)
	# Return output byte list
	return out_byte_list

####################################################################################################
#[Function]: Execute the action in main flow
#---------------------------------------------------------------------------------------------------
#[Parameters]: N/A
#[Return]: N/A
####################################################################################################
def main():
	# Get device id of the switch controller device (ert-swc)
	global sys
	dev_id_str = sys.argv[1]
	dev_id = convert_str2hex(dev_id_str, 4)
	# Initiate the connection with the switch controller
	swc_comm = ert_swc_rm()
	swc_comm.write_ute(dev_id)    # Register GW into device
	# Close connection
	swc_comm.finalize()
	time.sleep(2)

####################################################################################################
# Run the main flow
####################################################################################################
if __name__ == '__main__':
	main()

print("Finished registering to Switch Controller.")
print("Confirm if STAT light on ERT-SWC-RM device is turned green for a while, the registration is successful.")