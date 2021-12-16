import sys, os
sys.path.append(os.path.abspath(os.getcwd() + '/openblock_gateway/communicators/localstorage/'))
from database_interface import local_storage
import logging
from constant import *
import constant
from configuration import *
from json_interface import set_device_directions
from .function_library import *
from datetime import datetime
import configparser
import csv
import glob
import time

def init_database(logger):
    # Start initiating database to create tables
    database = local_storage(logger=logger)
    # Create "rooms" table
    room_table = {
        'roomId': 'PRIMARY KEY',
    }
    database.create_table("rooms", room_table)
    # Create "devices" table
    device_table = {
        'source': 'text',
        'devId': 'PRIMARY KEY',
        'slaveId': 'PRIMARY KEY',
        'channelId': 'PRIMARY KEY',
        'protocol': 'int',
        'room': 'text',
        'status': 'int',
        'type': 'text',
        'direction': 'int',
        'position': 'int',
        'valueType': 'int',
        'co2Hex': 'text',
        'co2Dec': 'int',
        'co2Sup': 'int',
        'inverted': 'int',
        'relatedSource': 'text',
        'ctlCode': 'int',
        'ctlCo2Min': 'int',
        'ctlCo2Max': 'int',
        'ctlDelayOn': 'int',
        'ctlDelayOff': 'int',
        'mldDelayOn': 'int',
        'mldDelayOff': 'int'
    }
    database.create_table("devices", device_table)
    # Create "data" table
    data_table = {
        'source': 'text',
        'devId': 'PRIMARY KEY',
        'slaveId': 'PRIMARY KEY',
        'channelId': 'PRIMARY KEY',
        'data': 'text',
        'co2_value': 'int'
    }
    database.create_table("data", data_table)
    # End initiating database
    database.close()
#[END OF FUNCTION][init_database]#######################################################################################

def init_logging():
    # Create logger
    logger = logging.getLogger('gateway_logger')
    logger.setLevel(logging.DEBUG)
    # Create handler to configure behavior of logger
    logger_handler = logging.handlers.RotatingFileHandler(LOG_FILE_NAME, mode='a', maxBytes=5*1024*1024,
                                                             backupCount=2, encoding=None, delay=0)
    logger_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(FORMAT)
    logger_handler.setFormatter(formatter)
    # Add handler to the logger
    logger.addHandler(logger_handler)
    # Return Logger
    return logger
#[END OF FUNCTION][init_logging]########################################################################################

def get_mac_addr(network_interface, logger):
    try:
        # Go to system file and look up for MAC address according to Interface
        interface_path = '/sys/class/net/' + network_interface + '/address'
        net_info = open(interface_path)
        # Get the MAC address
        mac_addr = net_info.readline()
        # Convert all lower-case characters to upper-case
        mac_addr = mac_addr.upper()
        logger.info ('[Init] Successfully obtained the default MAC address: ' + str(mac_addr[0:17]))
    except Exception as err:
        # Fail to get MAC due to inputted Interface
        mac_addr = "AD:A1:23:12:31:23"
        logger.error ('[Init] Not able to get MAC address of Gateway, error: ' + str(err))
    return mac_addr[0:17]
#[END OF FUNCTION][get_mac_addr]########################################################################################

def get_rooms_on_init_message(database_connection):
    list_of_rooms = database_connection.query_data("rooms")
    list_room_to_process = {}
    for room_info in list_of_rooms:
        list_room_to_process[room_info[RM__ROOM_ID]] = 0
    return list_of_rooms, list_room_to_process
#[END OF FUNCTION][get_rooms_on_init_message]###########################################################################

def get_devices_to_process_on_init_message(database_connection, room, room_info, list_room_to_process, logger):
    # Get room 
    room_id = ''
    list_of_devices_to_process_EnOcean = []
    list_of_devices_to_process_Modbus = []
    list_of_devices = {}
    # Get and save the new room into rooms table
    if ('room_id' in room_info.keys()) and (room_info['room_id'] != ''):
        room_id = room_info['room_id']
        room_to_database = room(room_id, logger=logger)
        room_to_database.save()
    else:
        logger.error("[get devices] Failed to add the new room in the message from cloud, Room Id field is invalid")
    # Make list of devices needed to be processes, and catogorize them into EnOcean and Modbus
    try:
        list_room_to_process[room_id] = 1
        data_to_process = {'room' : room_id}
        list_of_devices_of_database = database_connection.query_data("devices", data_to_process)

        for device_info in list_of_devices_of_database:
            # Can remove the IDs based on source_id
            list_of_devices[device_info[DV__SC_ID]] = 0
            if device_info[DV__EN_DV_ID] == 'NULL':
                # Modbus device
                list_of_devices_to_process_Modbus.append(device_info)
            elif device_info[DV__MB_SV_ID] == 'NULL':
                # EnOcean device
                list_of_devices_to_process_EnOcean.append(device_info)
    except Exception as lst_err:
        logger.error("[get devices] Failed to get devices list in a room, error: " + str(lst_err))
    return list_of_devices_to_process_EnOcean, list_of_devices_to_process_Modbus, list_of_devices
#[END OF FUNCTION][get_devices_to_process_on_init_message]##############################################################

def get_devices_to_database_on_init_message(database_connection, room_info, logger):
    devices_to_database = []
    flag_device_control = False
    # Handle sensor devices
    if ('devices' in room_info.keys()):
        for device in room_info['devices']:
            try:
                device_to_database = {}         # look for this
                # Can remove the ifs
                device_to_database['source_id'] = str(device['source_id'])
                device_to_database['room'] = room_info['room_id']
                device_to_database['protocol'] = device['protocol']
                device_to_database['type'] = device['type']
                device_to_database['direction'] = set_device_directions(device['type'])
                # Data related to CO2 sensors
                device_to_database['position'] = 0
                device_to_database['valueType'] = 0
                device_to_database['co2Hex'] = 'NULL'
                device_to_database['co2Dec'] = 0
                device_to_database['co2Sup'] = 0
                # Data related to control process
                device_to_database['related_source_id'] = "NULL"
                # Get Ids in case of EnOcean devices
                if 'device_id' in device.keys():
                    device_to_database['device_id'] = str(device['device_id'])
                    if 'related_source_id' in device.keys():
                        device_to_database['related_source_id'] = device['related_source_id']
                # Get Ids in case of Modbus devices
                elif 'slave_address' in device.keys():
                    if 'read_address' in device.keys():
                        device_to_database['read_address'] = str(device['read_address'])
                    elif 'write_address' in device.keys():
                        device_to_database['write_address'] = str(device['write_address'])
                        flag_device_control = True
                    device_to_database['slave_address'] = str(device['slave_address'])
                    device_to_database['inverted'] = 0
                elif 'device_id' not in device.keys() and 'slave_address' not in device.keys():
                    # If there is no device id and no slave id, skip this item
                    continue
                # Specific for CO2 sensors, add field of CO2 sensor position (Indoor/Outdoor)
                if 'd_position' in device.keys():
                    device_to_database['position'] = device['d_position']
                # Specific for GMW83DRP sensor, add sub field of GMW83DRP sensor determine 3 type of data: (Temperature/Humidity/CO2 concentration)
                if 'v_type' in device.keys():
                    device_to_database['valueType'] = device['v_type']
                # Specific for CO2 sensors, add field of CO2 sensor HEX range
                if 'hex' in device.keys():
                    device_to_database['co2Hex'] = device['hex']
                # Specific for CO2 sensors, add field of CO2 sensor DEC range
                if 'value' in device.keys():
                    device_to_database['co2Dec'] = device['value']
                # Specific for CO2 sensors, add field of CO2 sensor complement value
                if 'add_value' in device.keys():
                    device_to_database['co2Sup'] = device['add_value']
                # Insert device info into device_to_database list, preparing to save to database
                devices_to_database.append(device_to_database)
                # logger.debug ("[get devices] Device to database: " + str(device_to_database))
            except Exception as err:
                logger.error("[get devices] Error on saving device to database, error: " + str(err))
    # Control devices
    if ('control_devices' in room_info.keys()):
        # Prepare configuration related to room
        # Create default values
        room_configs = {
            'd_time_on': REQUIRED_CTL_REQ_NO,
            'd_time_off': REQUIRED_CTL_REQ_NO
        }
        # Collect configuration data from cloud if valid
        if 'settings' in room_info.keys():
            if 'd_time_on' in room_info['settings'].keys() and type(room_info['settings']['d_time_on']) == int:
                room_configs['d_time_on'] = room_info['settings']['d_time_on']
            if 'd_time_off' in room_info['settings'].keys() and type(room_info['settings']['d_time_off']) == int:
                room_configs['d_time_off'] = room_info['settings']['d_time_off']
        # Collect information of devices related to control operation
        for device in room_info['control_devices']:
            try:
                # Insert controlled device, if controlling info is available
                devices_to_database = get_control_devices_to_save_to_database(devices_to_database, device, room_info['room_id'], room_configs)
                # Insert tracking device, if tracking info is available
                devices_to_database = get_tracking_devices_to_save_to_database(devices_to_database, device, room_info['room_id'])
            except Exception as err:
                logger.error("[get devices] Error on saving control device to database, error: " + str(err))
    return devices_to_database
#[END OF FUNCTION][get_devices_to_database_on_init_message]#############################################################

def get_control_devices_to_save_to_database(devices_to_database, device, room_id, control_settings):
    source_id = device['source_id']
    # Control device over enocean channel
    if 'device_id' in device.keys() and 'chanel' in device.keys():
        control_eno_device_to_database = {}
        control_eno_device_to_database['source_id'] = source_id
        control_eno_device_to_database['device_id'] = str(device['device_id'])
        control_eno_device_to_database['write_address'] = str(device['chanel'])
        control_eno_device_to_database['protocol'] = str(device['protocol'])
        control_eno_device_to_database['type'] = str(device['type'])
        control_eno_device_to_database['room'] = room_id
        control_eno_device_to_database['position'] = 0
        control_eno_device_to_database['valueType'] = 0
        control_eno_device_to_database['direction'] = 1
        control_eno_device_to_database['inverted'] = 0
        control_eno_device_to_database['related_source_id'] = 'NULL'
        # control_eno_device_to_database['position'] = 'NULL'
        # Get other setting for control
        control_eno_device_to_database['ctlDelayOn'] = REQUIRED_CTL_REQ_NO
        control_eno_device_to_database['ctlDelayOff'] = REQUIRED_CTL_REQ_NO
        if 'd_time_on' in control_settings.keys():
            control_eno_device_to_database['ctlDelayOn'] = control_settings['d_time_on']
        if 'd_time_off' in control_settings.keys():
            control_eno_device_to_database['ctlDelayOff'] = control_settings['d_time_off']
        control_eno_device_to_database['ctlCo2Min'] = 0
        control_eno_device_to_database['ctlCo2Max'] = 0
        control_eno_device_to_database['mldDelayOn'] = REQUIRED_MLD_REQ_NO
        control_eno_device_to_database['mldDelayOff'] = REQUIRED_MLD_REQ_NO
        if 'settings' in device.keys():
            for info_obj in device['settings']:
                if isinstance(info_obj, dict):
                    if ('ctrl_co2_min' in info_obj.keys()) and (info_obj['ctrl_co2_min'] > 0) and ((control_eno_device_to_database['ctlCo2Min'] == 0) or (info_obj['ctrl_co2_min'] < control_eno_device_to_database['ctlCo2Min'])):
                        control_eno_device_to_database['ctlCo2Min'] = info_obj['ctrl_co2_min']
                    if ('ctrl_co2_max' in info_obj.keys()) and (info_obj['ctrl_co2_max'] > 0) and ((control_eno_device_to_database['ctlCo2Max'] == 0) or (info_obj['ctrl_co2_max'] < control_eno_device_to_database['ctlCo2Max'])):
                        control_eno_device_to_database['ctlCo2Max'] = info_obj['ctrl_co2_max']
                    # Get delay time
                    if 'd_time_on' in info_obj.keys():
                        control_eno_device_to_database['mldDelayOn'] = info_obj['d_time_on']
                    if 'd_time_off' in info_obj.keys():
                        control_eno_device_to_database['mldDelayOff'] = info_obj['d_time_off']
        ##  Import EnOcean - Control device into the device list from database
        devices_to_database.append(control_eno_device_to_database)
    # Control device over modbus channel
    elif 'slave_address' in device.keys() and 'write_address' in device.keys():
        # Split control device info from cloud into 2 rows, getting info for control part
        ## Control part
        inverted_value_write = device['is_write_inverted']
        control_mbs_device_to_database = {}
        control_mbs_device_to_database['source_id'] = source_id
        control_mbs_device_to_database['slave_address'] = str(device['slave_address'])
        control_mbs_device_to_database['write_address'] = str(int(device['write_address']) + 20)
        control_mbs_device_to_database['protocol'] = str(device['protocol'])
        control_mbs_device_to_database['type'] = str(device['type'])
        control_mbs_device_to_database['room'] = room_id
        control_mbs_device_to_database['position'] = 0
        control_mbs_device_to_database['valueType'] = 0
        control_mbs_device_to_database['direction'] = 1
        # control_mbs_device_to_database['position'] = 'NULL'
        if inverted_value_write == 'True':
            control_mbs_device_to_database['inverted'] = 1
        else:
            control_mbs_device_to_database['inverted'] = 0
        control_mbs_device_to_database['related_source_id'] = 'NULL'
        # Get other setting for control
        control_mbs_device_to_database['ctlDelayOn'] = REQUIRED_CTL_REQ_NO
        control_mbs_device_to_database['ctlDelayOff'] = REQUIRED_CTL_REQ_NO
        if 'd_time_on' in control_settings.keys():
            control_mbs_device_to_database['ctlDelayOn'] = control_settings['d_time_on']
        if 'd_time_off' in control_settings.keys():
            control_mbs_device_to_database['ctlDelayOff'] = control_settings['d_time_off']
        control_mbs_device_to_database['ctlCo2Min'] = 0
        control_mbs_device_to_database['ctlCo2Max'] = 0
        control_mbs_device_to_database['mldDelayOn'] = REQUIRED_MLD_REQ_NO
        control_mbs_device_to_database['mldDelayOff'] = REQUIRED_MLD_REQ_NO
        if 'settings' in device.keys():
            for info_obj in device['settings']:
                if isinstance(info_obj, dict):
                    if ('ctrl_co2_min' in info_obj.keys()) and (info_obj['ctrl_co2_min'] > 0) and ((control_mbs_device_to_database['ctlCo2Min'] == 0) or (info_obj['ctrl_co2_min'] < control_mbs_device_to_database['ctlCo2Min'])):
                        control_mbs_device_to_database['ctlCo2Min'] = info_obj['ctrl_co2_min']
                    if ('ctrl_co2_max' in info_obj.keys()) and (info_obj['ctrl_co2_max'] > 0) and ((control_mbs_device_to_database['ctlCo2Max'] == 0) or (info_obj['ctrl_co2_max'] < control_mbs_device_to_database['ctlCo2Max'])):
                        control_mbs_device_to_database['ctlCo2Max'] = info_obj['ctrl_co2_max']
                    # Get delay time
                    if 'd_time_on' in info_obj.keys():
                        control_mbs_device_to_database['mldDelayOn'] = info_obj['d_time_on']
                    if 'd_time_off' in info_obj.keys():
                        control_mbs_device_to_database['mldDelayOff'] = info_obj['d_time_off']
        ###  Import Control part into the device list from database
        devices_to_database.append(control_mbs_device_to_database)
    # Return the list of devices shall be saved to database
    return devices_to_database
#[END OF FUNCTION][get_control_devices_to_save_to_database]#############################################################

def get_tracking_devices_to_save_to_database(devices_to_database, device, room_id):
    source_id = device['source_id']
    if 'slave_address' in device.keys() and 'read_address' in device.keys():
        # Split control device info from cloud into 2 rows, getting info for tracking part
        ## Tracking part
        inverted_value_read = device['is_read_inverted']
        tracking_device_to_database = {}
        tracking_device_to_database['source_id'] = source_id
        tracking_device_to_database['slave_address'] = str(device['slave_address'])
        tracking_device_to_database['read_address'] = str(device['read_address'])
        tracking_device_to_database['protocol'] = str(device['protocol'])
        tracking_device_to_database['type'] = str(device['type']) + '-tracking'
        tracking_device_to_database['room'] = room_id
        tracking_device_to_database['position'] = 0
        tracking_device_to_database['valueType'] = 0
        tracking_device_to_database['direction'] = 2
        tracking_device_to_database['co2Hex'] = 'NULL'
        tracking_device_to_database['co2Dec'] = 0
        tracking_device_to_database['co2Sup'] = 0
        # tracking_device_to_database['position'] = 'NULL'
        if inverted_value_read == 'True':
            tracking_device_to_database['inverted'] = 1
        else:
            tracking_device_to_database['inverted'] = 0
        tracking_device_to_database['related_source_id'] = 'NULL'
        ### Import Tracking part into the device list from database
        devices_to_database.append(tracking_device_to_database)
    # Return the list of devices shall be saved to database
    return devices_to_database
#[END OF FUNCTION][get_tracking_devices_to_save_to_database]############################################################

def set_database_with_devices_on_init_message(room_info, database_connection, data, devices, devices_to_database,\
     list_of_devices_to_process_Modbus, list_of_devices_to_process_EnOcean, logger, list_of_devices, enoCommunicator, modbusCommunicator, is_on_bootup):
    is_error = False
    deleted_eno_out_dev_list = {}
    deleted_mb_out_dev_list = []
    for device_to_database in devices_to_database:
        try:
            # logger.debug("[get devices] saving device to database : " + str(device_to_database))
            # process database based on source id
            list_of_devices[device_to_database['source_id']] = 1

            if 'device_id' in device_to_database.keys():
                # process enocean devices
                list_of_devices_to_process_EnOcean = set_database_with_enocean_devices(list_of_devices_to_process_EnOcean, device_to_database, devices, data, is_on_bootup, logger)
            elif 'slave_address' in device_to_database.keys() :
                # process modbus devices
                list_of_devices_to_process_Modbus = set_database_with_modbus_devices(list_of_devices_to_process_Modbus, device_to_database, devices, data, is_on_bootup, logger)
        except Exception as mk_lst_err:
            logger.error("[get devices] Error on making list of devices to save, error: " + str(mk_lst_err))
            is_error = True

    # delete devices that are not used in the room anymore
    for device_EnOcean in list_of_devices_to_process_EnOcean:
        try:
            # Get channel of EnOcean device if any
            channel = ''
            data_to_process = {
                'source': device_EnOcean[DV__SC_ID],
                'devId' : device_EnOcean[DV__EN_DV_ID],
                'room' : room_info["room_id"]
            }
            if device_EnOcean[DV__CHN_ID] != 'NULL':
                channel = device_EnOcean[DV__CHN_ID]
                data_to_process['channelId'] = channel
            # Push device info to output device list based on direction field for turning off unused output
            if device_EnOcean[DV__DIRECTION] == 1:
                device_id = device_EnOcean[DV__EN_DV_ID]
                # If device id of SWC not exist in current device insert an element in the dictionary of control devices
                if device_id not in deleted_eno_out_dev_list.keys():
                    deleted_eno_out_dev_list[device_id] = []
                command = device_EnOcean + (CONTROL_OFF, )
                # Push the device item into the list of devices connected to SWC channels
                deleted_eno_out_dev_list[device_id].append(command)
            # Delete out of data of EnOcean device in database
            database_connection.delete_data("devices", data_to_process)
            # Delete related data
            data_to_delete = data(devid=device_EnOcean[DV__EN_DV_ID], channelid=channel)
            # data_to_delete.source_id = device_EnOcean[DV__SC_ID]
            data_to_delete.delete()
        except Exception as dl_en_err:
            logger.error("[get devices] Error on deleting enocean data, error: " + str(dl_en_err))
            is_error = True
    for device_modbus in list_of_devices_to_process_Modbus:
        try:
            data_to_process = {
                'source': device_modbus[DV__SC_ID],
                'slaveId' : device_modbus[DV__MB_SV_ID],
                'channelId' : device_modbus[DV__CHN_ID],
                'room' : room_info["room_id"]
            }
            if device_modbus[DV__TYPE] == 'gmw83drp-sensor':
                data_to_process['valueType'] = device_modbus[DV__VAL_TYPE]
            # Push device info to output device list based on direction field for turning off unused output
            if device_modbus[DV__DIRECTION] == 1:
                # Convert to list to update
                command_info = list(device_modbus)
                command_info[DV__INVERTED] = 0   # Ignore inverted mode, turn the output coil to OFF
                # Combine with reset value into final command tuple
                command = tuple(command_info) + (CONTROL_OFF, )
                deleted_mb_out_dev_list.append(command)
            # Delete out of data of Modbus device data in database
            database_connection.delete_data("devices", data_to_process)
            # Delete related data
            data_to_delete = data(slaveid=device_modbus[DV__MB_SV_ID], channelid=device_modbus[DV__CHN_ID])
            # data_to_delete.source_id = device_modbus[DV__SC_ID]
            data_to_delete.delete()
        except Exception as dl_mb_err:
            logger.error("[get devices] Error on deleting modbus data, error: " + str(dl_mb_err))
            is_error = True
    # Turn off the unused EnOcean output channels
    if len(deleted_eno_out_dev_list) != 0:
        try:
            enoCommunicator.handle_writing_request(deleted_eno_out_dev_list, True)
        except:
            logger.error("[get devices] Failed to turned of the , error: " + str(dl_mb_err))
    # Turn off the unused Modbus output channels
    if len(deleted_mb_out_dev_list) != 0:
        for modbus_output in deleted_mb_out_dev_list:
            try:
                modbusCommunicator.write_data(modbus_output)
            except:
                logger.error("[get devices] Failed to turned of the , error: " + str(dl_mb_err))
                continue
    if not is_error:
        return True
    else:
        logger.error("[get devices] Failed to modify the devices in database")
        return False
#[END OF FUNCTION][set_database_with_devices_on_init_message]###########################################################

def process_modbus_device(list_of_devices_to_process_Modbus, slave_address, channelAdressId):
    i = 0
    return_list = []
    for modbus_device in list_of_devices_to_process_Modbus:
        if modbus_device[DV__MB_SV_ID] == slave_address and modbus_device[DV__CHN_ID] == channelAdressId:
            list_of_devices_to_process_Modbus.pop(i)
        i = i + 1
    return_list = list_of_devices_to_process_Modbus
    return return_list
#[END OF FUNCTION][process_modbus_device]###############################################################################

def process_enocean_device(list_of_devices_to_process_EnOcean, device_id, channelAdressId):
    i = 0
    return_list = []
    for eno_device in list_of_devices_to_process_EnOcean:
        if eno_device[DV__EN_DV_ID] == device_id and eno_device[DV__CHN_ID] == channelAdressId:
            list_of_devices_to_process_EnOcean.pop(i)
        i = i + 1
    return_list = list_of_devices_to_process_EnOcean
    return return_list
#[END OF FUNCTION][process_enocean_device]##############################################################################

def set_database_with_modbus_devices(list_of_devices_to_process_Modbus, device_to_database, devices, data, is_on_bootup, logger):
    if 'read_address' in device_to_database.keys():
        # Handle sensors
        device_save = devices(sourceid=device_to_database['source_id'], slaveid=device_to_database['slave_address'], channelid=device_to_database['read_address'], logger=logger)
        # Reset device status for following changes
        if is_on_bootup or (device_save.room != device_to_database['room']) or (device_save.inverted != device_to_database['inverted']) or \
         (device_save.position != device_to_database['position']) or (device_save.value_type != device_to_database['valueType']):
            device_save.status = 2
            # Clean data in database
            try:
                clean_data = data(sourceid=device_to_database['source_id'], slaveid=device_to_database['slave_address'], channelid=device_to_database['read_address'], logger=logger)
                clean_data.delete()
            except:
                # Failed to clean data
                pass
        # Update other fields in database
        device_save.protocol = device_to_database['protocol']
        device_save.room = device_to_database['room']
        device_save.type = device_to_database['type']
        device_save.direction = device_to_database['direction']
        device_save.position = device_to_database['position']
        device_save.value_type = device_to_database['valueType']
        device_save.co2_hex = device_to_database['co2Hex']
        device_save.co2_dec = device_to_database['co2Dec']
        device_save.co2_sup = device_to_database['co2Sup']
        device_save.inverted = device_to_database['inverted']
        device_save.related_source_id = 'NULL'

        slave_address = device_to_database['slave_address']
        read_address = device_to_database['read_address']
        list_of_devices_to_process_Modbus = process_modbus_device(list_of_devices_to_process_Modbus, slave_address, read_address)
        if device_save.save() == True:
            logger.debug ("[get devices] Saved device " + str (device_to_database['source_id']) + " to database")
        else :
            logger.error ("[get devices] Cannot save device " + str (device_to_database['source_id']) + " to database")

    elif ('write_address' in device_to_database.keys()):
        # Handle controller modules
        device_save = devices(sourceid=device_to_database['source_id'], slaveid=device_to_database['slave_address'], channelid=device_to_database['write_address'], logger=logger)
        # Reset device status for following changes
        if (device_save.room != device_to_database['room']):
            device_save.status = 2
            # Clean data in database
            try:
                clean_data = data(sourceid=device_to_database['source_id'], slaveid=device_to_database['slave_address'], channelid=device_to_database['write_address'], logger=logger)
                clean_data.delete()
            except:
                # Failed to clean data
                pass
        # Update other fields in database
        device_save.protocol = device_to_database['protocol']
        device_save.room = device_to_database['room']
        device_save.type = device_to_database['type']
        device_save.direction = device_to_database['direction']
        device_save.position = device_to_database['position']
        device_save.value_type = device_to_database['valueType']
        device_save.inverted = device_to_database['inverted']
        device_save.related_source_id = 'NULL'
        if 'ctlCo2Min' in device_to_database.keys():
            device_save.ctl_co2_min = device_to_database['ctlCo2Min']
        if 'ctlCo2Max' in device_to_database.keys():
            device_save.ctl_co2_max = device_to_database['ctlCo2Max']
        if 'ctlDelayOn' in device_to_database.keys():
            device_save.ctl_delay_on = device_to_database['ctlDelayOn']
        if 'ctlDelayOff' in device_to_database.keys():
            device_save.ctl_delay_off = device_to_database['ctlDelayOff']
        if 'mldDelayOn' in device_to_database.keys():
            device_save.mld_delay_on = device_to_database['mldDelayOn']
        if 'mldDelayOff' in device_to_database.keys():
            device_save.mld_delay_off = device_to_database['mldDelayOff']

        slave_address = device_to_database['slave_address']
        write_address = device_to_database['write_address']
        list_of_devices_to_process_Modbus = process_modbus_device(list_of_devices_to_process_Modbus, slave_address, write_address)
        if device_save.save() == True:
            logger.debug ("[get devices] Saved device " + str (device_to_database['source_id']) + " to database")
        else :
            logger.error ("[get devices] Cannot save device " + str (device_to_database['source_id']) + " to database")
    else:
        device_save = devices(sourceid=device_to_database['source_id'], slaveid=device_to_database['slave_address'], channelid="", logger=logger)
        # Update other fields in database
        device_save.protocol = device_to_database['protocol']
        device_save.room = device_to_database['room']
        device_save.type = device_to_database['type']
        device_save.direction = device_to_database['direction']
        device_save.position = device_to_database['position']
        device_save.value_type = device_to_database['valueType']
        device_save.inverted = device_to_database['inverted']
        device_save.related_source_id = 'NULL'
        slave_address = device_to_database['slave_address']
        list_of_devices_to_process_Modbus = process_modbus_device(list_of_devices_to_process_Modbus, slave_address, "NULL")
        if device_save.save() == True:
            logger.debug ("[get devices] Saved device " + str (device_to_database['source_id']) + " to database")
        else:
            logger.error ("[get devices] Cannot save device " + str (device_to_database['source_id']) + " to database")

    return list_of_devices_to_process_Modbus
#[END OF FUNCTION][set_database_with_modbus_devices]####################################################################

def set_database_with_enocean_devices(list_of_devices_to_process_EnOcean, device_to_database, devices, data, is_on_bootup, logger):
    if 'write_address' in device_to_database.keys():
        # Handle controller modules
        device_save = devices(sourceid=device_to_database['source_id'], devid=device_to_database['device_id'], channelid=device_to_database['write_address'], logger=logger)
        # Reset device status for following changes
        if (device_save.room != device_to_database['room']):
            device_save.status = 2
            # Clean data in database
            try:
                clean_data = data(sourceid=device_to_database['source_id'], devid=device_to_database['device_id'], channelid=device_to_database['write_address'], logger=logger)
                clean_data.delete()
            except:
                # Failed to clean data
                pass
        # Update other fields in database
        device_save.protocol = device_to_database['protocol']
        device_save.room = device_to_database['room']
        device_save.type = device_to_database['type']
        device_save.direction = device_to_database['direction']
        device_save.position = device_to_database['position']
        device_save.value_type = device_to_database['valueType']
        device_save.related_source_id = device_to_database['related_source_id']
        if 'ctlCo2Min' in device_to_database.keys():
            device_save.ctl_co2_min = device_to_database['ctlCo2Min']
        if 'ctlCo2Max' in device_to_database.keys():
            device_save.ctl_co2_max = device_to_database['ctlCo2Max']
        if 'ctlDelayOn' in device_to_database.keys():
            device_save.ctl_delay_on = device_to_database['ctlDelayOn']
        if 'ctlDelayOff' in device_to_database.keys():
            device_save.ctl_delay_off = device_to_database['ctlDelayOff']
        if 'mldDelayOn' in device_to_database.keys():
            device_save.mld_delay_on = device_to_database['mldDelayOn']
        if 'mldDelayOff' in device_to_database.keys():
            device_save.mld_delay_off = device_to_database['mldDelayOff']

        device_id = device_to_database['device_id']
        write_address = device_to_database['write_address']
        list_of_devices_to_process_EnOcean = process_enocean_device(list_of_devices_to_process_EnOcean, device_id, write_address)
        if device_save.save() == True:
            logger.debug ("[get devices] Saved device " + str (device_to_database['source_id']) + " to database")
        else :
            logger.error ("[get devices] Cannot save device " + str (device_to_database['source_id']) + " to database")

    else :
        # Handle sensors
        device_save = devices(sourceid=device_to_database['source_id'], devid=device_to_database['device_id'], logger=logger)
        # Reset device status for following changes
        if is_on_bootup:
            device_save.status = 2
        if (device_save.room != device_to_database['room']) or (device_save.position != device_to_database['position']) or \
         (device_save.related_source_id != device_to_database['related_source_id']):
            # Clean data in database
            device_save.status = 2
            try:
                clean_data = data(sourceid=device_to_database['source_id'], devid=device_to_database['device_id'], logger=logger)
                clean_data.delete()
            except:
                # Failed to clean data
                pass
        # Update other fields in database
        device_save.protocol = device_to_database['protocol']
        device_save.room = device_to_database['room']
        device_save.type = device_to_database['type']
        device_save.direction = device_to_database['direction']
        device_save.position = device_to_database['position']
        device_save.value_type = device_to_database['valueType']
        device_save.co2_hex = device_to_database['co2Hex']
        device_save.co2_dec = device_to_database['co2Dec']
        device_save.co2_sup = device_to_database['co2Sup']
        device_save.related_source_id = device_to_database['related_source_id']

        device_id = device_to_database['device_id']
        write_address = "NULL"
        list_of_devices_to_process_EnOcean = process_enocean_device(list_of_devices_to_process_EnOcean, device_id, write_address)
        if device_save.save() == True:
            logger.debug ("[get devices] Saved device " + str (device_to_database['source_id']) + " to database")
        else :
            logger.error ("[get devices] Cannot save device " + str (device_to_database['source_id']) + " to database")
    return list_of_devices_to_process_EnOcean
#[END OF FUNCTION][set_database_with_enocean_devices]###################################################################

def set_database_with_rooms_on_init_message(database_connection, data, list_room_to_process, logger, enoCommunicator, modbusCommunicator):
    is_error = False
    # Delete items related to rooms out of control
    for room_id in list_room_to_process.keys():
        try:
            if list_room_to_process[room_id] == 0:
                database_connection.delete_data("rooms", {"roomId" : room_id})
                data_to_process = {"room" : room_id}

                list_of_devices_to_delete = database_connection.query_data("devices", data_to_process)
                database_connection.delete_data("devices", data_to_process)

                eno_out_commands = {}
                for device_info in list_of_devices_to_delete:
                    try:
                        if device_info[DV__EN_DV_ID] == 'NULL':
                            # Turn off DO if it is DIO8R output channel
                            if device_info[DV__DIRECTION] == 1:
                                # Convert to list to update
                                command_info = list(device_info)
                                command_info[DV__INVERTED] = 0   # Ignore inverted mode, turn the output coil to OFF
                                # Combine with reset value into final command tuple then execute it
                                command = tuple(command_info) + (CONTROL_OFF,)
                                modbusCommunicator.write_data(command)
                            # Delete in data table
                            data_to_delete = data(slaveid=device_info[DV__MB_SV_ID], channelid=device_info[DV__CHN_ID], logger=logger)
                            data_to_delete.delete()
                        else :
                            device_id = device_info[DV__EN_DV_ID]
                            channel = ""
                            if device_info[DV__CHN_ID] != "NULL":
                                channel = device_info[DV__CHN_ID]
                            # Insert to output control device if it is output channel
                            if device_id not in eno_out_commands.keys():
                                eno_out_commands[device_id] = []
                            # Push the device item into the list of devices connected to SWC channels
                            commmand = device_info + (CONTROL_OFF,)
                            eno_out_commands[device_id].append(commmand)
                            # Delete in data table
                            data_to_delete = data(devid=device_info[DV__EN_DV_ID], channelid=channel, logger=logger)
                            data_to_delete.delete()
                    except Exception as data_dl_err:
                        is_error = True
                # Handle write output to EnOcean controller devices at once after collecting all control requests
                if len(eno_out_commands) != 0:
                    try:
                        enoCommunicator.handle_writing_request(eno_out_commands, True)
                    except Exception as err:
                        pass
        except Exception as rm_dl_err:
            is_error = True
    # Delete remaining data not related to any devices, or devices not related to any rooms
    try:
        remove_non_related_devices(database_connection, logger)
    except Exception as cl_err:
        is_error = True
    if not is_error:
        return True
    else:
        return False
#[END OF FUNCTION][set_database_with_rooms_on_init_message]#############################################################

def remove_non_related_devices(database_connection, logger):
    is_error = False
    # Find the devices within the room not in control
    ## At first, get list of all devices from database
    list_of_devices = database_connection.query_data("devices")
    off_rooms_list = []         # List of rooms still related to devices but have been removed
    checked_rooms_list = []     # Checklist of rooms
    ## Then, remove each device if related room is removed
    for device in list_of_devices:
        try:
            # Verify if room of device not in control by checking with "rooms" table in database
            room_id = device[DV__ROOM]
            if room_id not in checked_rooms_list:
                checked_rooms_list.append(room_id)
                room_data = {'roomId': device[DV__ROOM]}
                # Check for related room in "rooms" table
                db_room = database_connection.query_data("rooms", room_data)
                # If related room is removed from database, put it into off_rooms_list
                if (len(db_room) == 0):
                    off_rooms_list.append(room_id)
            # Delete the device if related room is removed from database
            if room_id in off_rooms_list:
                # Get queried keys
                queried_data = {}
                if device[DV__EN_DV_ID] != "NULL" and device[DV__EN_DV_ID] != "":
                    queried_data["devId"] = device[DV__EN_DV_ID]            # Device ID if EnOcean device
                if device[DV__MB_SV_ID] != "NULL" and device[DV__MB_SV_ID] != "":
                    queried_data["slaveId"] = device[DV__MB_SV_ID]          # Slave ID if EnOcean device
                if device[DV__CHN_ID] != "NULL" and device[DV__CHN_ID] != "":
                    queried_data["channelId"] = device[DV__CHN_ID]      # Channel ID if any
                # Delete the device
                database_connection.delete_data("devices", queried_data)
        except Exception as dv_err:
            logger.error ("[get devices] Failed to delete out of used device, error: " + str(dv_err))
            is_error = True
    # Find the data with the devices not in control
    list_of_data = database_connection.query_data("data")
    for device_info in list_of_data:
        try:
            queried_data = {}
            if device_info[DT__EN_DV_ID] != "NULL" and device_info[DT__EN_DV_ID] != "":
                queried_data["devId"] = device_info[DT__EN_DV_ID]           # Device ID if EnOcean device
            if device_info[DT__MB_SV_ID] != "NULL" and device_info[DT__MB_SV_ID] != "":
                queried_data["slaveId"] = device_info[DT__MB_SV_ID]         # Slave ID if EnOcean device
            if device_info[DT__CHN_ID] != "NULL" and device_info[DT__CHN_ID] != "":
                queried_data["channelId"] = device_info[DT__CHN_ID]     # Channel ID if any
            # Query the device from database - "devices" table
            db_device = database_connection.query_data("devices", queried_data)
            # If related device is removed from database, delete the data row in database - "data" table
            if len(db_device) == 0:
                database_connection.delete_data("data", queried_data)
        except Exception as dt_err:
            logger.error ("[get devices] Failed to delete out of used data, error: " + str(dt_err))
            is_error = True
    # Return result
    if not is_error:
        return True
    else:
        return False
#[END OF FUNCTION][remove_non_related_devices]##########################################################################

def update_camera_folders(database_connection, ftp_server_path, logger):
    # Get list of room from database
    db_queried_rooms = database_connection.query_data("rooms", {})
    db_rooms = []
    folder_exist = False
    folders_list = []
    # Format the list of rooms
    for result in db_queried_rooms:
        if result[RM__ROOM_ID] != "" and result[RM__ROOM_ID] != "NULL":
            db_rooms.append(result[RM__ROOM_ID])
    # Check if ftp_server folder not exists then create it
    try:
        folder_exist = os.path.isdir(ftp_server_path)
        if not folder_exist:
            os.makedirs(ftp_server_path)
        # List out the list of folder exists in ftp shared folder
        folders_list = os.listdir(ftp_server_path)
    except Exception as getfld_err:
        logger.error("[get devices] Failed to check folder of storing camera images, error: " + str(getfld_err))
    # Add new rooms connected to GW
    for room in db_rooms:
        try:
            if room not in folders_list:
                # Create new folder
                full_path_add_name = ftp_server_path + "/" + room
                logger.info("[get devices] Add folder of room " + str(room) + " in directory used for storing camera images")
                os.mkdir(full_path_add_name)
                time.sleep(0.001)
                # Grant full permission for every type of user to operate on this folder
                os.chmod(full_path_add_name, 0o777)
        except Exception as mkdir_err:
            logger.error("[get devices] Failed to add folder of new room in directory used for storing camera images, error: " + str(mkdir_err))
#[END OF FUNCTION][udpate_camera_folders]###############################################################################

def init_tracking_file(logger):
    # Enable logging
    logger.info('[app-tracking] Create file tracking')
    list_of_columns = ['Time', 'Room', 'Co2Out', 'Temperature', 'Humidity', 'Co2In', 'Influenza', 'Tuberculosis', 'Measles', 'Covid']
    # Checking if tracking file has already existed then remove it
    if os.path.isfile(TRACKING_FILE):
        logger.info('[app-tracking] File tracking has already existed, going to replace it')
        os.remove(TRACKING_FILE)
    # Create new tracking file
    with open(TRACKING_FILE, mode='a') as tracking_file:
        tracking_writer = csv.writer(tracking_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        tracking_writer.writerow(list_of_columns)
        logger.info('[app-tracking] New data is updated to tracking file')
#[END OF FUNCTION][init_tracking_file]##################################################################################

def check_reboot(logger):
    # Get last reboot info from storing file
    last_reboot = read_file(REBOOT_TRACKFILE)
    # Set limit time to allow reboot
    dateTimeObj = datetime.now()
    current_time = int(dateTimeObj.strftime('%s'))
    reboot_limit = current_time
    # Add delay if just rebooted lately
    if (last_reboot != None) and (last_reboot.isnumeric()) and (int(last_reboot) < current_time):
        reboot_limit += REBOOT_LONG_DELAY * 60
    # Checking if tracking file has already existed then remove it
    remove_file(REBOOT_TRACKFILE)
    return reboot_limit
#[END OF FUNCTION][check_reboot]#######################################################################################