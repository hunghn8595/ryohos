import json
import time
import crc8
import logging
from constant import *

def parse_raw_data(raw_data):
    length_of_message = len(raw_data)
    # Convert received data into Integer type
    i = 0
    for byte in raw_data:
        raw_data[i] = ord(byte)
        i = i + 1
    # Determine if it is data of ERT SWC device
    device_type = ""
    if raw_data[2] == 0x05 and raw_data[3] == 0x0A and raw_data[4] == 0x07:
        device_type = "ert-swc-sensor"
        if raw_data[6] != 0x06 and raw_data[7] != 0x50:
            return {"id": "NONVALID", "values": "NONVALID"}
    # Convert received data in to String type
    cat_data = ''
    for byte in raw_data:
        cat_data += '{0:0{1}X}'.format(byte, 2)
    # Handle separate parts of data frame
    ## Handle for ERT-SWC type
    if device_type == "ert-swc-sensor":
        ## Define position of device id
        start_data_position = 6*2
        end_data_position = start_data_position + 2*2
        ## Define position of data value
        start_id_position = 15*2
        end_id_position = start_id_position + 4*2
    ## Handle for other types
    else:
        ## Define position of device id
        start_data_position = 6*2
        start_id_position = start_data_position + 1*2
        if length_of_message > 18:
            start_id_position = start_data_position + (length_of_message - 18)*2
        end_id_position = start_id_position + 4*2
        ## Define position of data value
        start_data_position = end_id_position
        end_data_position = start_data_position + 3*2
    # Get the device ID
    id_device = cat_data[start_id_position:end_id_position]
    data_to_get = ""
    device_detail = {}
    device_detail["id"] = id_device # hex(id_device)
    # Get the needed content from the data part
    data_to_get = cat_data[start_data_position:end_data_position]
    device_detail["values"] = data_to_get # hex(data_to_get)
    return device_detail

def shift_left_number(start_bit, end_bit):
    result = 0
    for i in range(start_bit, end_bit+1):
        result = result + 2 ** i
    return int(result)

def validate_data(data_frame, logger):
    # Exit immediately if the data length is not appropriate
    # On basic frame when the length of the whole data frame is 19, the position of CRC of data is 15
    frame_len = len(data_frame)
    is_len_correct = True
    if frame_len <= 7:
        return False
    lenght_field_1 = ord(data_frame[2])
    lenght_field_2 = ord(data_frame[3])
    lenght_field_3 = ord(data_frame[4])
    device_type = ""
    if lenght_field_1 == 0x05 and lenght_field_2 == 0x0A and lenght_field_3 == 0x07:
        device_type = "ert-swc-sensor"
        if frame_len != 22:
            is_len_correct = False
    else:
        cal_length = 7 + lenght_field_2 + lenght_field_3
        if frame_len != cal_length:
            is_len_correct = False
    # Length of data frame is invalid, escape function
    if not is_len_correct:
        # logger.error("[EnOcean] Enocean Communicator received data frame with false length")
        return False
    # Validate CRC
    ## Handle specifically for ERT-SWC device type
    if device_type == "ert-swc-sensor":
        # Check CRC of Header
        header = bytearray()
        # Extract the header and its CRC from the DATA Frame
        for byte in data_frame[1:5]:
            header += byte
        header_crc = data_frame[5]
        # Execute confirming the header with CRC
        if confirm_crc(header, header_crc) == False:
            logger.error("[EnOcean] Received Data with false Header CRC")
            return False
        # Check CRC of Data
        main_data = bytearray()
        for byte in data_frame[6:(frame_len-1)]:
            main_data += byte
        data_crc = data_frame[frame_len-1]
        # Execute confirming the header with CRC
        if confirm_crc(main_data, data_crc) == False:
            logger.error("[EnOcean] Received Data with false Data CRC")
            return False
    ## Handle for other EnOcean device types
    else:
        data_crc_pos = frame_len - 4
        # Check CRC of Header
        header = bytearray()
        # Extract the header and its CRC from the DATA Frame
        for byte in data_frame[1:5]:
            header += byte
        header_crc = data_frame[5]
        # Execute confirming the header with CRC
        if confirm_crc(header, header_crc) == False:
            logger.error("[EnOcean] Received Data with false Header CRC")
            return False
        # Check CRC of Data
        main_data = bytearray()
        for byte in data_frame[6:data_crc_pos]:
            main_data += byte
        data_crc = data_frame[data_crc_pos]
        # Execute confirming the header with CRC
        if confirm_crc(main_data, data_crc) == False:
            logger.error("[EnOcean] Received Data with false Data CRC")
            return False
        # Check CRC of Option
        option = bytearray()
        for byte in data_frame[(frame_len-3):(frame_len-1)]:
            option += byte
        option_crc = data_frame[frame_len-1]
        # Execute confirming the header with CRC
        if confirm_crc(option, option_crc) == False:
            logger.error("[EnOcean] Received Data with false Option CRC")
            return False
    # If all CRC is checked OK, return True to notify that Data Frame is OK
    return True

def confirm_crc(data, crc_bytes):
    # Convert CRC in DATA frame from byte into string in lowercase format
    crc_bytes = '{0:0{1}X}'.format(ord(crc_bytes), 2)
    crc_bytes = crc_bytes.lower()
    # Init CRC checking operator
    hash = crc8.crc8()
    hash.update(data)
    result = hash.hexdigest()
    # Compare the CRC to the result
    if result == crc_bytes:
        return True
    else:
        return False
