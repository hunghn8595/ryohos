import sys, os
sys.path.append(os.path.abspath(os.getcwd() + '/openblock_gateway/communicators/localstorage/'))
import threading
import logging
import time
# import constant
import configparser
import requests

from .constant import *
from configuration import *
from logging.handlers import RotatingFileHandler
from database_interface import local_storage
from json_interface import set_device_directions
from ..communicators.localstorage.DevicesModel import devices
from ..communicators.localstorage.RoomModel import room
from ..communicators.localstorage.DataModel import data
from ..communicators.localstorage.database_interface import local_storage

'''
Functions for main flow
'''

####################################################################################################
#[Function]: Filter devices in database by Source Id
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   device_info {dict} - Information of the device, containing Source ID, new control status requested from cloud...
#   logger {logging} - Logging operator object
#[Return]:
#   obj {tuple} - Object containing information of the controlled device queried by Source ID
####################################################################################################
def scid_2_data(device_info={}, logger=""):
    global devices
    try:
        # Validate source id
        if "source_id" in device_info.keys():
            source_id = device_info['source_id']
        else:
            return ()
        # Validate value to set
        if "status_id" in device_info.keys():
            new_data = device_info['status_id']
        else:
            new_data = CONTROL_OFF
        # Validate control type
        if "type_id" in device_info.keys():
            control_type = device_info['type_id']
        else:
            control_type = CTL_TYPE_USUAL
        # Validate control type
        if "control_id" in device_info.keys():
            control_id = device_info['control_id']
        else:
            control_id = 0
        # Query device from database - devices table
        query_device = devices(sourceid=source_id, logger=logger)
        query_device.dev_id = ''
        query_device.slave_id = ''
        query_device.channel_id = ''
        query_device.direction = 0
        query_device.protocol = 0
        query_device.room = ''
        query_device.type = ''
        dev_obj = query_device.get_data()
        # Scan queried result for control device
        if len(dev_obj) != 0:
            for obj in dev_obj:
                temp_obj_list = list(obj)
                temp_obj_list[DV__CTL_ID] = control_id
                obj = tuple(temp_obj_list)
                # Determine control device by direction field with value as 1
                if obj[DV__DIRECTION] == 1:
                    # control_type = 1 with normal control, control_type = 2 with instant control
                    if control_type == CTL_TYPE_INSTANT:
                        if new_data == CONTROL_ON:
                            new_data = CONTROL_ON_IMD
                        elif new_data == CONTROL_OFF:
                            new_data = CONTROL_OFF_IMD
                    elif control_type == CTL_TYPE_UPDATE:
                        new_data = CONTROL_OFF_RMV
                    # Add requested value to make the request message
                    obj += (new_data, )
                    return obj
    except Exception as err:
        logger.error('[Control_output] Failed to get controlled device info. Error: ' + str(err))
    return ()

####################################################################################################
#[Function]: Handle the control message receiced from cloud
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   message {dict} - Control message received from cloud
#   logger {logging} - Logging operator object
#[Return]:
#   list_control {list} - List of information of controlled devices
#   instant_list {dict} - List of information of instantly controlled devices
####################################################################################################
def make_dev_list_from_control_msg(message, logger):
    list_control = []
    instant_list = {}
    try:
        if ('data' in message.keys()) and len(message['data']) != 0:
            for device in message['data']:
                # Confirm variable type of device object
                if isinstance(device, dict):
                    # Confirm data model of control message received from cloud
                    if 'source_id' in device.keys() and 'status_id' in device.keys() :
                        # Based on source id, get the device info in table device from database, and add requested value to object's end
                        dev_info = scid_2_data(device, logger)
                        if dev_info != ():
                            # logger.debug("[Control_output] Append to control request list: " + str(dev_info))
                            list_control.append(dev_info)
                            # In case of instant demand, prepare the list of demand to return. Otherwise, keep it empty
                            if 'type_id' in device.keys() and device['type_id'] == CTL_TYPE_INSTANT:
                                source_id = device['source_id']
                                instant_list[source_id] = device['status_id']
                        else:
                            logger.debug("[Control_output] Device is not in scope of management of this Gateway, Source ID: " + str(device['source_id']))
                    else:
                        logger.error('[Control_output] Failed to get controlled device info. Error: False data model - ' + str(device))
                else:
                    logger.error('[Control_output] Failed to get controlled device info. Error: False data type - ' + str(type(device)))
    except Exception as err:
        logger.error('[Control_output] Failed to make list of controlled devices, error: ' + str(err))
    # Return the list of devices
    return list_control, instant_list

'''
Functions for EnOcean, Modbus Communication and Operation
'''

####################################################################################################
#[Function]: Read a tuple of data, and get the value by position, if invalid then return none
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   input_object {tuple} - data package on which data is extracted from
#   info_position {int} - position of the data to get out from the tuple
#   default_value {logging} - default value return in case unable to get the data, or invalid data
#[Return]:
#   output_value {any} - the value gotten from data package
####################################################################################################
def get_info(input_object=(), info_position=0, default_value=None):
    output_value = None
    if len(input_object) == 0 or len(input_object) < info_position:
        return default_value
    output_value = input_object[info_position]
    return output_value

####################################################################################################
#[Function]: Print log of a frame of byte in HEX format
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   input_message {str} - Message content for logging
#   input_frame {list} - List of bytes
#   logger {logging} - Logging operator object
#[Return]: N/A
####################################################################################################
def log_byte_list(input_message="", input_frame=[], logger=""):
    cat_data = ""
    total_content = ""
    try:
        for byte in input_frame:
            cat_data += '{0:0{1}X}'.format(byte, 2)
        total_content = str(input_message) + " " + str(cat_data)
        logger.debug(total_content)
    except Exception as lg_err:
        logger.error("[logger] Failed to show log, error: " + str(lg_err))

####################################################################################################
#[Function]: Convert HEX string data into DECIMAL int value
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   hex_input {str} - Input value in HEX string format
#   logger {logging} - Logging operator object
#[Return]:
#   converted_dec {int} - decimal value converted from input HEX value
####################################################################################################
def hex_2_dec(hex_input="0000", logger=""):
    converted_dec = CO2_IGNORE_VL
    if type(hex_input) != str or hex_input == "NULL" or hex_input == "":
        return converted_dec
    hex_formatted = "0x" + hex_input
    try:
        converted_dec = int(hex_formatted, base=16)
    except Exception as err:
        logger.error("[logger] Failed to calculate co2 value, error: " + str(err))
    return converted_dec

####################################################################################################
#[Function]: Calculate CO2 value from raw data
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   input_raw {int} - Input raw value
#   raw_range {list} - Range of the raw value
#   result_range {int} - Range for Co2 value
#   sup_value {list} - Complement value
#   logger {logging} - Logging operator object
#[Return]: 
#   co2_result {int} - CO2 final value
####################################################################################################
def calculate_co2(input_raw=0, raw_range=0, result_range=0, sup_value=0, logger=""):
    co2_result = 0
    if raw_range == 0:
        # The raw_range cannot be 0 as it is the dividend
        return co2_result
    try:
        # Convert raw data from reading range into decimal range by proportion and then add the additional value
        co2_result = int(input_raw / raw_range * result_range) + sup_value
    except Exception as err:
        logger.error("[logger] Failed to calculate co2 value, error: " + str(err))
    return co2_result

'''
Functions for common Operations
'''

####################################################################################################
#[Function]: Create a loop of async processes
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   process_function {func} - the callback function which would be called in the loop of threads
#   input_arguments {dict} - input arguments used by the callback function
#[Return]: N/A
####################################################################################################
def make_async_loop(process_function, input_arguments={}):
    # Check if input function is valid
    if not callable(process_function):
        return
    # Make a processing thread
    new_process = threading.Thread(target=process_function, args=(make_async_loop, input_arguments))
    new_process.start()

####################################################################################################
#[Function]: Create a timer wait for a flag to change to expected value
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   flag {bool} - the flag that is checked currently
#   expected_value {bool} - expected value of the flag
#   timeout {int} - timeout to force end timer
#[Return]: N/A
####################################################################################################
def wait_flag_changed(flag=False, expected_value=False, timeout=0):
    # Escape function if input invalid
    if type(flag) != type(expected_value):
        return False
    # Loop until flag is changed to expected value of reach timeout
    count_time = 0
    while flag != expected_value and count_time < timeout*1000:
        count_time += 1
        time.sleep(0.001)

####################################################################################################
#[Function]: Check internet connection status
#---------------------------------------------------------------------------------------------------
#[Parameters]: N/A
#[Return]: N/A
####################################################################################################
def check_connection():
    try:
        # Try to ping google.com to check the internet
        r = requests.get('https://www.google.com/', timeout=3)
        return True
    except requests.ConnectionError as ex:
        return False

####################################################################################################
#[Function]: Write to file
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   file_path {str} - path to file
#   input_data {str} - input data
#[Return]: 
#   Result {bool} - Result of file writing process
####################################################################################################
def write_to_file(file_path, input_data):
    try:
        # Open the file, create new if not exists, then write new data and finally close it
        file_process = open(file_path, mode="a+")
        file_process.write(input_data)
        file_process.close()
        return True
    except Exception as err:
        return False

####################################################################################################
#[Function]: Read from file
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   file_path {str} - path to file
#[Return]: 
#   Result {str} - Result of file reading process
####################################################################################################
def read_file(file_path):
    try:
        if os.path.isfile(file_path):
            # If not exists, open the file, then read data and finally close it
            file_process = open(file_path, mode="r")
            read_data = file_process.readline()
            file_process.close()
            return read_data
        else:
            return None
    except Exception as err:
        return None

####################################################################################################
#[Function]: Remove file
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   file_path {str} - path to file
#[Return]: 
#   Result {bool} - Result of file removing process
####################################################################################################
def remove_file(file_path):
    if os.path.isfile(file_path):
        os.remove(file_path)
        return "File is removed"
    else:
        return "No file to remove"

####################################################################################################
#[Function]: Check the status of the module to determine the result of controlling is ligit
#---------------------------------------------------------------------------------------------------
#[Parameters]:
#   channel_info {tuple} - information of the channel related to the controlling module needs checking
#[Return]:
#   result {bool} - the status of the controlling module
####################################################################################################
def get_module_status(channel_info=()):
    # Prepare variables
    result = False
    if len(channel_info) == 0:
        return result
    control_module = None;
    # Input data of module for querying data
    if channel_info[DV__MB_SV_ID] == 'NULL':
        # In case of enocean ERT-SWC module
        control_module = devices(devid=channel_info[DV__EN_DV_ID], channelid='NULL')
        # control_module.type = 'ert-swc-sensor'
    elif channel_info[DV__EN_DV_ID] == 'NULL':
        # In case of modbus WMB-DIO8R module
        control_module = devices(slaveid=channel_info[DV__MB_SV_ID], channelid='NULL')
        # control_module.type = 'wmb-dio8r-modbus'
    # Query data from database
    module_data = control_module.get_data()
    # Check current status
    if len(module_data) >= 0:
        for module in module_data:
            if module[DV__STATUS] == DEV_STT_CONN:
                result = True
    return result
