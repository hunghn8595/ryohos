import serial
import sys
import time
import crc8

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
	#[Function]: Make and send request message to unlock the Switch controller
	#---------------------------------------------------------------------------------------------------
	#[Parameters]:
	#   self {ert_swc_rm} - The ERT-SWC-RM device handler object
	#   devid {str} - Device ID of the ERT-SWC-RM device
	#[Return]:
	#   result {bool} - Message of unlocking ERT-SWC-RM device
	####################################################################################################
	def unlock_command(self, devid):
		# Escape fucntion if input Device ID is invalid
		if len(devid) < 4:
			return []
		# Define constances
		HEADER_START_OFFSET = 1
		CRCH_OFFSET = 5
		DATA_START_OFFSET = 6
		DEVICEID_OFFSET = 14
		CRCD_OFFSET = 24
		# Create the data frame for unlocking the SWC device
		unlock_data = [0x55, 0x00, 0x08, 0x0A, 0x07, 0xC6, 0x00, 0x01, 0x07, 0xFF, 0x02, 0x63, 0x28, 0x80, 0xAA, 0xAA, 0xAA, 0xAA, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xC5]
		# Overwrite Device ID
		for i in range(4):
			unlock_data[DEVICEID_OFFSET + i] = devid[i]
		# Calculate CRC for header and data frames
		unlock_data[CRCH_OFFSET] = make_crc(unlock_data[HEADER_START_OFFSET:CRCH_OFFSET]) # Calculate header's CRC
		unlock_data[CRCD_OFFSET] = make_crc(unlock_data[DATA_START_OFFSET:CRCD_OFFSET]) # Calculate data's CRC
		# Print out log of the full frame of UTE registration message
		# cat_data = ''
		# for byte in unlock_data:
		# 	cat_data += ' ' + '{0:0{1}X}'.format(byte, 2)
		# print('Sent unlock data frame which is:' + str(cat_data))
		# Return the unlock message that is sent to ERT-SWC-RM device
		return unlock_data

	####################################################################################################
	#[Function]: Make and send request message to turn on/off channels the Switch controller
	#---------------------------------------------------------------------------------------------------
	#[Parameters]:
	#   self {ert_swc_rm} - The ERT-SWC-RM device handler object
	#   devid {str} - Device ID of the ERT-SWC-RM device
	#   ctrl {int|hex formatted} - Mask of the requested output value on channels
	#[Return]:
	#   result {list} - Mssage of controlling ERT-SWC-RM device
	####################################################################################################
	def onoff_command(self, devid, ctrl):
		# Escape fucntion if input Device ID is invalid
		if len(devid) < 4:
			return []
		# Constants of Data offset postion
		HEADER_START_OFFSET = 1
		CRCH_OFFSET = 5
		DATA_START_OFFSET = 6
		CTRL_OFFSET = 10
		DEVICEID_OFFSET = 11
		CRCD_OFFSET = 21
		# Create data template
		ctrl_data = [0x55, 0x00, 0x05, 0x0A, 0x07, 0x57, 0x03, 0x50, 0x00, 0x31, 0x00, 0xAA, 0xAA, 0xAA, 0xAA, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xB6]
		# Overwrite Control value
		ctrl_data[CTRL_OFFSET] = 0x0F & ctrl
		# Overwrite Device ID
		for i in range(4):
			ctrl_data[DEVICEID_OFFSET + i] = devid[i]
		# Calculate CRC for header and data frames
		ctrl_data[CRCH_OFFSET] = make_crc(ctrl_data[HEADER_START_OFFSET:CRCH_OFFSET]) # Calculate header's CRC
		ctrl_data[CRCD_OFFSET] = make_crc(ctrl_data[DATA_START_OFFSET:CRCD_OFFSET]) # Calculate data's CRC
		# Print out log of the full frame of UTE registration message
		cat_data = ''
		for byte in ctrl_data:
			cat_data += ' ' + '{0:0{1}X}'.format(byte, 2)
		print('Sent on/off control data frame which is:' + str(cat_data))
		# Return the onoff message that is sent to ERT-SWC-RM device
		return ctrl_data

	####################################################################################################
	#[Function]: Operate the output on the SWC channels
	#---------------------------------------------------------------------------------------------------
	#[Parameters]:
	#   self {ert_swc_rm} - The ERT-SWC-RM device handler object
	#   device_id {str} - device id of the SWC device
	#   output_value {str} - message for sending
	#[Return]: N/A
	####################################################################################################
	def request_control(self, device_id, output_value):
		# Unlock the SWC device
		# Conduct the control message
		unlock_msg = self.unlock_command(device_id)
		# Send unlock message to the SWC device
		try:
			self.eno_comm.write(unlock_msg)
		except Exception as ulk_err:
			print('Sending unlock request failed, error: ' + str(ulk_err))
			return False
		time.sleep(1)
		# Conduct the control message
		onoff_msg = self.onoff_command(device_id, output_value)
		# Send Command to turn ON/OFF channels
		try:
			self.eno_comm.write(onoff_msg)
			return True
		except Exception as ctl_err:
			print('Sending on/off request failed, error: ' + str(ctl_err))
			return False

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
	# Constants of byte mask to control SWC channels
	CH1_ON = 0x01
	CH2_ON = 0x02
	CH3_ON = 0x04
	CH4_ON = 0x08
	ALL_ON = 0x0F
	ALL_OFF = 0x00
	# Get device id of the switch controller device (ert-swc-rm)
	global sys
	dev_id_str = sys.argv[1]
	dev_id = convert_str2hex(dev_id_str, 4)
	# Initiate the connection with the switch controller
	swc_comm = ert_swc_rm()
	# Turn on only channel 1 of ERT-SWC-RM
	print("Command: Only CH1 is ON")
	swc_comm.request_control(dev_id, CH1_ON)
	time.sleep(2)
	# Turn off all channels of ERT-SWC-RM
	print("Command: All CH are OFF")
	swc_comm.request_control(dev_id, ALL_OFF)
	time.sleep(2)
	# Close connection
	swc_comm.finalize()

####################################################################################################
# Run the main flow
####################################################################################################
if __name__ == '__main__':
	main()

print("Finished testing channels of Switch Controller.")