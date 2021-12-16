import time
import crc8
from constant import *
from ..utils.function_library import *

####################################################################################################
#[Function]: Get mask of byte depending on the input channel's value to calculate the control byte
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   channel {str} - The channel of SWC device
#   value {int} - The value on the channel
#[Return]: N/A
#   byte_mask {int|hex formatted} - The mask of byte
####################################################################################################
def get_byte_mask(channel='', value=2):
    # Make input param
    demand = str(channel)
    if (int(value) == 1):
        demand += '_ON'
    else:
        demand += '_OFF'
    # Return the mask in each case for channels and ON/OFF value
    if   demand == "1_ON":     return 0x01     # Channel 1 is ON
    elif demand == "1_OFF":    return 0x0E     # Channel 1 is OFF
    elif demand == "2_ON":     return 0x02     # Channel 2 is ON
    elif demand == "2_OFF":    return 0x0D     # Channel 2 is OFF
    elif demand == "3_ON":     return 0x04     # Channel 3 is ON
    elif demand == "3_OFF":    return 0x0B     # Channel 3 is OFF
    elif demand == "4_ON":     return 0x08     # Channel 4 is ON
    elif demand == "4_OFF":    return 0x07     # Channel 4 is OFF
    else:                      return 0x00     # All 4 channels are OFF

####################################################################################################
#[Function]: Apply mask of byte depending on the input channel's value to calculate the control byte
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   origin_value {int|hex formatted} - The value on the channel before calculating
#   byte_mask {int|hex formatted} - The mask of byte
#   value_to_set {int} - The value to set on the channel
#[Return]: N/A
#   out_val {int|hex formatted} - The calculated output value
####################################################################################################
def apply_mask(out_val=0x00, mask=0x00, value_to_set=CONTROL_OFF):
    # Not apply in case mask is 0x00
    if mask != 0x00:
        if(int(value_to_set) == CONTROL_ON):
            # Turn on a channel and keep the others unchanged
            out_val |= mask
        else:
            # Turn off a channel and keep the others unchanged
            out_val &= mask
    return out_val

####################################################################################################
#[Function]: Make and send request message to unlock the Switch controller
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   devid {str} - Device ID of the ERT-SWC device
#   logger {logging} - Logging operator object
#[Return]:
#   result {bool} - Message of unlocking SWC device
####################################################################################################
def unlock_command(devid, logger):
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
    unlock_data[CRCH_OFFSET] = make_crc(unlock_data[HEADER_START_OFFSET:CRCH_OFFSET], logger) # Calculate header's CRC
    unlock_data[CRCD_OFFSET] = make_crc(unlock_data[DATA_START_OFFSET:CRCD_OFFSET], logger) # Calculate data's CRC
    # Print log of unlock message
    # log_byte_list("[EnOcean] Going to send unlock data frame =", unlock_data, logger)
    # Return the unlock message that is sent to ERT-SWC device
    return unlock_data

####################################################################################################
#[Function]: Make and send request message to turn on/off channels the Switch controller
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   devid {str} - Device ID of the ERT-SWC device
#   ctrl {int|hex formatted} - Mask of the requested output value on channels
#   logger {logging} - Logging operator object
#[Return]:
#   result {list} - Mssage of controlling SWC device
####################################################################################################
def onoff_command(devid, ctrl, logger):
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
    ctrl_data[CRCH_OFFSET] = make_crc(ctrl_data[HEADER_START_OFFSET:CRCH_OFFSET], logger) # Calculate header's CRC
    ctrl_data[CRCD_OFFSET] = make_crc(ctrl_data[DATA_START_OFFSET:CRCD_OFFSET], logger) # Calculate data's CRC
    # Print log of unlock message
    log_byte_list("[EnOcean] Going to send ONOFF data =", ctrl_data, logger)
    # Return the onoff message that is sent to ERT-SWC device
    return ctrl_data

####################################################################################################
#[Function]: Request status from ERT-SWC device
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   devid {str} - Device ID of the ERT-SWC device
#   logger {logging} - Logging operator object
#[Return]:
#   result {int} - result of status request attempt
####################################################################################################
def get_sts_command(devid, logger):
    # Escape fucntion if input Device ID is invalid
    if len(devid) < 4:
        return []
    # Constants of Data offset postion
    HEADER_START_OFFSET = 1
    CRCH_OFFSET = 5
    DATA_START_OFFSET = 6
    DEVICEID_OFFSET = 11
    CRCD_OFFSET = 21
    # Escape function if input Device ID is invalid
    if len(devid) < 4:
        return []
    # Create data template
    sts_data = [0x55, 0x00, 0x05, 0x0A, 0x07, 0x57, 0x03, 0x52, 0x00, 0x31, 0x00, 0xAA, 0xAA, 0xAA, 0xAA, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x7B]
    # Overwrite Device ID
    for i in range(4):
        sts_data[DEVICEID_OFFSET + i] = devid[i]
    # Calculate CRC for header and data frames
    sts_data[CRCH_OFFSET] = make_crc(sts_data[HEADER_START_OFFSET:CRCH_OFFSET], logger) # calculate header's CRC
    sts_data[CRCD_OFFSET] = make_crc(sts_data[DATA_START_OFFSET:CRCD_OFFSET], logger) # calculate data's CRC
    # Print log of unlock message
    # log_byte_list("[EnOcean] Going to send status requesting data frame =", sts_data, logger)
    # Return the status requesting message that is sent to ERT-SWC device
    return sts_data

####################################################################################################
#[Function]: Calculate CRC checksum for a frame of data
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   data {str} - The frame of data needed to calculate CRC
#   logger {logging} - Logging operator object
#[Return]: N/A
####################################################################################################
def make_crc(data, logger):
    # Convert input data from int into HEX format
    temp = bytearray()
    for byte in data:
        temp += byte.to_bytes(1, 'big')
    # Calculate and make CRC
    hash = crc8.crc8()
    hash.update(temp)
    result = hash.hexdigest()
    # Compare the CRC to the result
    # log_byte_list("[EnOcean] Going to send status requesting data frame =", result, logger)
    # Convert CRC from string to HEX formatted int
    hex_result = convert_str2hex(result, 1, logger)
    return hex_result[0]

####################################################################################################
#[Function]: Convert a string into Hex formatted data list
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   input_str {str} - Message for converting
#[Return]: N/A
#   out_val {list} - The list of calculated converted data
####################################################################################################
def convert_str2hex(input_str, expected_len, logger):
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
            logger.error("Failed to convert string to HEX data, error: " + str(err))
    else:
        logger.error("Input string has false length. Please input string with correct lentgh as " + str(expected_len * step))
    # In case failing to convert, return a list sample
    default_mask = 0xAA
    for i in range(expected_len):
        out_byte_list.append(default_mask)
    # Return output byte list
    return out_byte_list