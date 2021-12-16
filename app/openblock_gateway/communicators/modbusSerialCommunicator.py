from datetime import datetime
import time
import threading
import logging
from threading import Thread
from constant import *
from configuration import *
from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from pymodbus.register_read_message import ReadWriteMultipleRegistersResponse
from .localstorage.database_interface import local_storage
from .localstorage.DevicesModel import devices
from .localstorage.DataModel import data
from ..utils.function_library import *

class modbusCommunicator(Thread):
    # Modbus Communicator base-class.
    client = None

    ####################################################################################################
    #[Function]: Initiate modbus communicator
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #   ttyPath {str} - Path to the ttySXXX file
    #   baudrate {int} - Baud rate of the serial port
    #[Return]: N/A
    ####################################################################################################
    def __init__(self, ttyPath, baudRate, logger):
        # Init instance
        self.logger = logger
        self.logger.info('[Modbus] Initiation: Configuring modbus serial port')
        super(modbusCommunicator, self).__init__()
        # Create a list to hold the devices that this gateway manages
        self.devices_in_control = []
        self.output_channels = []
        self.previous_outputs = {}
        # self.verified_outputs = {}
        # Create a thread to watch the change of devices status
        self.status_list = {}
        self.status_watcher = threading.Thread(name='check_status', target=self.check_status, args=())
        # Create a thread to maintain output value of output devices
        self.output_channel_keeper = threading.Thread(name='keeping_output', target=self.keep_output_value, args=())
        self.reading_speed = MODBUS_READING_SLEEP_TIME
        # Create connection on the modbus serial port
        try:
            self.client = ModbusClient(method = "rtu", port=ttyPath, stopbits = 1, bytesize = 8, parity = 'N', baudrate= baudRate, timeout= 1)
            self.client.connect()
            if self.client.is_socket_open():
                self.logger.info("[Modbus] Serial port " + ttyPath + ' is enabled')
            else:
                self.logger.info("[Modbus] Serial port " + ttyPath + ' is not enabled')
        except Exception as err:
            self.logger.error("[Modbus] Serial port " + ttyPath + ' is not valid, error: ' + str(err))
            self.client = ModbusClient()

    ####################################################################################################
    #[Function]: Check connection from Gateway to Modbus controllers and retry if disconnected
    #---------------------------------------------------------------------------------------------------
    #[Parameters]: N/A
    #[Return]: result {boolean} - response status of connection
    ####################################################################################################
    def check_connection(self):
        # Exit if Modbus communication is not available
        for attempt in range(3):
            if self.client.is_socket_open() == False:
                self.client.connect()
                time.sleep(1)
            else:
                return True
                break
        # Return failed result of current connection
        return False

    ####################################################################################################
    #[Function]: Request to read data from a AI device
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #   register_address {str} - address of the first register needed to be read
    #   registers_count {int} - amount of the registers needed to be read
    #   slave_id {int} - id of the sensor in modbus network
    #[Return]: result {tuple} - response data from port
    ####################################################################################################
    def read_AI(self, register_address=0, registers_count=1, slave_id=1):
        # Execute reading input registers request to AI slave device
        # self.logger.debug("[Modbus] Read AI - slave_id: " + str(slave_id) + ", register_address: " + str(register_address + 1) + ", register_count: " + str(registers_count))
        if self.check_connection() == True:
            try:
                result = self.client.read_input_registers(address=register_address, count=registers_count, unit=slave_id)
                return result
            except Exception as err:
                self.logger.error("[Modbus] Failed to read Analog Input, error: " + str(err))
        else:
            self.logger.info('[Modbus] Modbus network is disconnected, cannot read Analog Input')
        return None

    ####################################################################################################
    #[Function]: Request to read data from a DI device
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #   register_address {str} - address of the first register needed to be read
    #   registers_count {int} - amount of the registers needed to be read
    #   slave_id {int} - id of the sensor in modbus network
    #[Return]: result {tuple} - response data from port
    ####################################################################################################
    def read_DI(self, register_address=0, registers_count=1, slave_id=1):
        # Execute reading input registers request to DI slave device
        # self.logger.debug("[Modbus] Read DI - slave_id: " + str(slave_id) + ", register_address: " + str(register_address + 1) + ", register_count: " + str(registers_count))
        if self.check_connection() == True:
            try:
                result = self.client.read_discrete_inputs(address=register_address, count=registers_count, unit=slave_id)
                return result
            except Exception as err:
                self.logger.error("[Modbus] Failed to read Digital Input, error: " + str(err))
        else:
            self.logger.info('[Modbus] Modbus network is disconnected, cannot read Digital Input')
        return None

    ####################################################################################################
    #[Function]: Request to read data from a DO device
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #   coil_address {str} - address of the first register needed to be read
    #   coils_count {int} - amount of the registers needed to be read
    #   slave_id {int} - id of the sensor in modbus network
    #[Return]: result {tuple} - response data from port
    ####################################################################################################
    def read_DO(self, coil_address=0, coils_count=1, slave_id=1):
        # Execute reading input registers request to AI slave device
        # self.logger.debug("[Modbus] Read DO - slave_id: " + str(slave_id) + ", coil_address: " + str(coil_address + 1) + ", coils_count: " + str(coils_count))
        if self.check_connection() == True:
            try:
                result = self.client.read_coils(address=coil_address, count=coils_count, unit=slave_id)
                return result
            except Exception as err:
                self.logger.error("[Modbus] Failed to read Digital Output, error: " + str(err))
        else:
            self.logger.info('[Modbus] Modbus network is disconnected, cannot read Digital Output')
        return None

    ####################################################################################################
    #[Function]: Request to write data to a DO channel
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #   coil_address {str} - address of the coil needed to be written
    #   set_value {int} - wanted value
    #   slave_id {int} - id of the sensor in modbus network
    ####################################################################################################
    def write_DO(self, coil_address=0, set_value=0, slave_id=1):
        # Convert set value into HEX formatted string to show log
        hex_value = '{0:0{1}X}'.format(set_value, 4)
        # self.logger.debug("[Modbus] Write DO - slave_id: " + str(slave_id) + ", coil_address: " + str(coil_address + 1) + ", set_value: " + str(hex_value))
        # Execute reading input registers request to AI slave device
        if self.check_connection() == True:
            try:
                result = self.client.write_coil(address=coil_address, value=set_value, unit=slave_id)
                return result
            except Exception as err:
                self.logger.error("[Modbus] Failed to write Digital Output, error: " + str(err))
        else:
            self.logger.info('[Modbus] Modbus network is disconnected, cannot read Digital Output')
        return None

    ####################################################################################################
    #[Function]: Collect all Modbus devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #[Return]: N/A
    ####################################################################################################
    def collect_devices(self):
        try:
            # Update list of sensor devices
            self.update_sensor_list()
            # Delay some time to reduce memory leak
            time.sleep(0.0001)
            # Update list of output devices
            self.update_output_dev_list()
        except Exception as mbs_dev_err:
            self.logger.error("[Modbus] Failed to update Modbus devices list, errors: " + str(mbs_dev_err))

    ####################################################################################################
    #[Function]: Collect data from devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #[Return]: N/A
    ####################################################################################################
    def update_sensor_list(self):
        # Get the Modbus sensors
        modbus_ai_devices = devices(protocol=MODBUS_SENSOR_PROTOCOL, logger=self.logger)
        self.devices_in_control = modbus_ai_devices.get_data()
        tracking_di_devices = devices(protocol=MODBUS_WMB_PROTOCOL, direction=2, logger=self.logger)
        tracking_devices = tracking_di_devices.get_data()
        self.devices_in_control += tracking_devices
        # self.logger.debug("[Modbus] Current managed devives list is " + str(self.devices_in_control))
        # Update status list due to sensors list
        self.update_sensor_status_list()

    ####################################################################################################
    #[Function]: Update sensors status managing list
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #[Return]: N/A
    ####################################################################################################
    def update_sensor_status_list(self):
        # Update status controlling list
        if len(self.devices_in_control) != 0:
            updated_list = {}
            try:
                # Loop to delete device in status controlling list if device is removed in managed devices list
                for key in self.status_list:
                    # key is source_id of the device
                    # Define temporary variables used for below process
                    is_restored = False
                    # Get info of current status object, including slave ID, channel ID
                    status_object = self.status_list[key]
                    current_slave_id = status_object[0]['slave_id']
                    channels_count = 0
                    channels_no = len(status_object)
                    # Define a list of current channels that may be removed by update on the UI
                    channels_removed = []
                    for channel_object in status_object:
                        channels_removed.append(channel_object['channel_id'])
                    # Check the current data has been updated
                    for managed_device in self.devices_in_control:
                        dev_source_id = managed_device[DV__SC_ID]
                        # Finish scanning device info in self.devices_in_control if attempts reaches the channels amount
                        if channels_count >= channels_no:
                            break
                        # In case matching source ID, continue checking slave ID and channel ID information
                        if key == dev_source_id:
                            is_restored = True
                            channels_count += 1
                            if current_slave_id == managed_device[DV__MB_SV_ID]:
                                if managed_device[DV__CHN_ID] in channels_removed:
                                    channels_removed.remove(managed_device[DV__CHN_ID])
                            else:
                                is_restored = False
                                break
                    # Restore the current status object, and remove channel out of date if any
                    if is_restored == True:
                        # Remove channel, scan all objects
                        if len(channels_removed) != 0:
                            for pos in range(len(status_object)):
                                # If channel of the object is included in the removed channels list, pop the object out of the list
                                if status_object[pos]['channel_id'] in channels_removed:
                                    status_object.pop(pos)
                        # Add the current object into the valid list
                        updated_list[key] = status_object
                    time.sleep(0.001)
                # Loop to add device in managed devices list to status controlling list
                for managed_device in self.devices_in_control:
                    # Skip tracking channels
                    if managed_device[DV__TYPE] in TRACKING_DEVICES_LIST:
                        continue
                    # Making temporary var to contain the ids
                    dev_source_id = managed_device[DV__SC_ID]
                    slave_id = managed_device[DV__MB_SV_ID]
                    chn_id = managed_device[DV__CHN_ID]
                    # Check if this device does not exist in status controlling list then add it
                    if not (dev_source_id in updated_list):
                        updated_list[dev_source_id] = [
                            {
                                "slave_id": slave_id,
                                "channel_id": chn_id,
                                "current_recv": False,
                                'fail_no': 2
                            }
                        ]
                    else:
                        is_new_item = True
                        new_item = {}
                        for dev in updated_list[dev_source_id]:
                            if (slave_id == dev["slave_id"] and chn_id == dev["channel_id"]):
                                is_new_item = False
                        if is_new_item:
                            new_item = {
                                "slave_id": slave_id,
                                "channel_id": chn_id,
                                "current_recv": False,
                                'fail_no': 2
                            }
                            updated_list[dev_source_id].append(new_item)
                    time.sleep(0.001)
                # Update latest status to self.status_list
                self.status_list = updated_list
                self.logger.info("[Modbus] Current devices status list is " + str(self.status_list))
            except Exception as err:
                self.logger.error("[Modbus] Not able to collect current modbus devices, error: " + str(err))

    ####################################################################################################
    #[Function]: Collect all Modbus output controlled devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #[Return]: N/A
    ####################################################################################################
    def update_output_dev_list(self):
        # Get the Modbus control devices
        modbus_controlled_devices = devices(protocol=MODBUS_WMB_PROTOCOL, direction=1, logger=self.logger)
        self.output_channels = modbus_controlled_devices.get_data()
        # self.logger.debug("[Modbus] Current output channel list is " + str(self.output_channels))

    ####################################################################################################
    #[Function]: Collect data from devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #[Return]: N/A
    ####################################################################################################
    def write_data(self, command_message):
        # self.logger.info("[Modbus] Write Digital Output data")
        # Prepare parameters to write output
        slave_id = int(get_info(command_message, DV__MB_SV_ID, 1))
        channel_addr = int(get_info(command_message, DV__CHN_ID, 21)) - 20 - 1
        is_inverted = int(get_info(command_message, DV__INVERTED, 21))
        value = int(get_info(command_message, DV__EX_PRT_1, CONTROL_OFF))
        # Invert the output value if inverted is set
        if is_inverted == 1:
            if value == CONTROL_ON:
                value = CONTROL_OFF
            else:
                value = CONTROL_ON
        # Convert value to HEX data
        set_value = 0x0000
        if value == CONTROL_ON:
            set_value = 0xFF00
        try:
            self.write_DO(channel_addr, set_value, slave_id)
        except Exception as err:
            self.logger.error("[Modbus] Not able write, error: " + str(err))

    ####################################################################################################
    #[Function]: Collect data from devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #[Return]: N/A
    ####################################################################################################
    def collect_data(self):
        # Declare variable to count fail requests
        fail_no = 0
        wait_time = MODBUS_READING_SLEEP_TIME
        # Loop to collect data from modbus devices
        while 1:
            # When there are modbus devices to manage in system, request to read data from them
            if ( len(self.devices_in_control) != 0 ):
                is_all_dev_response = True
                try:
                    for device in self.devices_in_control:
                        # Prepare filter parameter
                        device_source_id = get_info(device, DV__SC_ID, "")
                        slave_id = get_info(device, DV__MB_SV_ID, "")
                        channel_id = get_info(device, DV__CHN_ID, "")
                        is_inverted = get_info(device, DV__INVERTED, 0)
                        device_type = get_info(device, DV__TYPE, "")
                        value_type = get_info(device, DV__VAL_TYPE, 0)
                        position = get_info(device, DV__CO2_POS, 0)
                        co2_hex = get_info(device, DV__CO2_HEX, "0000")
                        co2_dec = get_info(device, DV__CO2_DEC, 0)
                        co2_sup = get_info(device, DV__CO2_SUP, 0)
                        is_error = False # Error flag marks the case where error occurs
                        # Handle checking wmb-ai8-modbus and wmb-dio8r-modbus type devices
                        if ( device_type == 'wmb-ai8-modbus' or device_type == 'wmb-dio8r-modbus' ):
                            try:
                                channel_id = 0x0000
                                result_data = self.read_AI(channel_id, 1, int(slave_id))
                                is_connected = "not connected"
                                # Check if received response successfully
                                if ( hasattr(result_data, 'function_code') ):
                                    is_connected = "connected"
                                    # Store status of wmb module
                                    if ( device_source_id in self.status_list ) and ( len(self.status_list[device_source_id]) != 0 ):
                                        for pos in range(len(self.status_list[device_source_id])):
                                            item = self.status_list[device_source_id][pos]
                                            if ( slave_id == item['slave_id'] and item['channel_id'] == 'NULL' ) and ( 'current_recv' in item ):
                                                self.status_list[device_source_id][pos]['current_recv'] = True
                                self.logger.info('[Modbus] Check status of ' + str(device_source_id) + ' at slave address - ' + str(slave_id) + ' is: ' + str(is_connected))
                            except Exception as wmb_err:
                                # If exception occurs, then mark error
                                is_error = True
                            # If error flag is set, add error log and note process reading fail to repeat reading request later
                            if is_error:
                                is_all_dev_response = False
                                self.logger.error('[Modbus] Not getting status of wmb module ' + str(device_source_id) + ' at slave ' + str(slave_id))
                        # Handle gmd20-sensor and gmw83drp-sensor type devices
                        elif ( device_type == 'gmd20-sensor' or device_type == 'gmw83drp-sensor' ):
                            try:
                                result_data = self.read_AI(int(channel_id) - 1, 1, int(slave_id))
                                # Check if received response successfully, and response contains the data stored in the request register
                                if ( hasattr(result_data, 'registers') and ( len(result_data.registers) != 0 )):
                                    raw_value = result_data.registers[0]
                                    # Prevent case no input making read data reaches almost 0xFFFF
                                    if int(raw_value) >= 65280:
                                        continue
                                    # Allow handling data, ignore too small data in abnormal cases
                                    elif ( int(raw_value) > 300 ):
                                        hex_value = "0x%0.4X" % (raw_value) # Convert data to string type and hexadecimal formatted
                                        self.logger.debug('[Modbus] Received Analog Input value: ' + str(hex_value) + ' from ' + str(device_source_id) + ' at coil - ' + str(channel_id))
                                        # Calculate the CO2 value
                                        co2_result = 0
                                        if ((device_type == 'gmd20-sensor') or (device_type == 'gmw83drp-sensor' and value_type == 1)) and (position == 2):
                                            co2_raw = int(raw_value)
                                            co2_hex = hex_2_dec(co2_hex, self.logger)
                                            co2_result = calculate_co2(co2_raw, co2_hex, co2_dec, co2_sup, self.logger)
                                        # Save device value to database
                                        data_to_put_database = data(sourceid=device_source_id, slaveid=str(slave_id), channelid=str(channel_id),\
                                                                devdata=str(hex_value), co2value=co2_result, logger=self.logger)
                                        data_to_put_database.save()
                                        # Confirm that received data from this device to support status updating process
                                        if ( device_source_id in self.status_list ) and ( len(self.status_list[device_source_id]) != 0 ):
                                            for pos in range(len(self.status_list[device_source_id])):
                                                item = self.status_list[device_source_id][pos]
                                                if ( slave_id == item['slave_id'] and channel_id == item['channel_id'] ) and ( 'current_recv' in item ):
                                                    self.status_list[device_source_id][pos]['current_recv'] = True
                                # Check if failed to receive response, or response does not contain the needed data, then mark error
                                else:
                                    is_error = True
                            except Exception as ai_err:
                                # If exception occurs, then mark error
                                is_error = True
                            # If error flag is set, add error log and note process reading fail to repeat reading request later
                            if is_error:
                                is_all_dev_response = False
                                self.logger.info('[Modbus] Not getting data from device ' + str(device_source_id) + ' at slave ' + str(slave_id) + ' and coil ' + str(channel_id))
                        # Handle air-purifier, uv-c-control tracking type devices
                        elif device_type in TRACKING_DEVICES_LIST:
                            try:
                                # self.logger.debug('[Modbus] Check status of tracking coil')
                                trk_value = 2
                                result_data = self.read_DI(int(channel_id) - 1, 1, int(slave_id))
                                # Check if received response successfully, and response contains the data stored in the request register
                                if hasattr(result_data, 'bits'):
                                    bl_value = result_data.bits[0]
                                    self.logger.info('[Modbus] Received Digital Input value: ' + str(bl_value) + ' from ' + str(device_source_id))
                                    # Refer to requested value stored in database
                                    if (bl_value==True and is_inverted!=1) or (bl_value==False and is_inverted==1):
                                        trk_value = 1
                                else:
                                    # Check if failed to read input, then mark error
                                    is_error = True
                                data_to_put_database = data(sourceid=device_source_id, slaveid=slave_id, channelid=channel_id, devdata=str(trk_value), logger=self.logger)
                                data_to_put_database.save()
                            except Exception as do_err:
                                # If exception occurs, then mark error
                                is_error = True
                            # If error flag is set, add error log and note process reading fail to repeat reading request later
                            if is_error:
                                is_all_dev_response = False
                                self.logger.info('[Modbus] Not able to read Digital Input ' + str(device_source_id) + ' at slave ' + str(slave_id) + ' and coil ' + str(channel_id))
                        # Delay between each time getting data
                        time.sleep(0.0001)
                except Exception as err:
                    self.logger.error("[Modbus] Not able to collect current modbus devices data, error: " + str(err))
                    is_all_dev_response = False
                # If get data normally, wait "wait_time" time to request data again, or it fails to get data for (fail_no x 0.5) second
                if (is_all_dev_response == False) and (fail_no < 2):
                    # If any devices does not respond, then request data again
                    fail_no += 1
                    wait_time = 0.5
                else:
                    # If get data from all the devices successfully, then wait for 20 seconds later to collect data again
                    # Or in case of collecting data from disconnected devices for 2 more times, reset all count data and collect all devices data normally again
                    fail_no = 0
                    wait_time = MODBUS_READING_SLEEP_TIME
                time.sleep(wait_time)
            # When there are no modbus devices to manage in system, go to sleep for 1 second then check again
            else:
                time.sleep(0.001)

    ####################################################################################################
    #[Function]: Checking connection of Modbus devices periodically
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #[Return]: N/A
    ####################################################################################################
    def check_status(self):
        self.logger.info("[Init][Modbus] Checking status Operator initiated")
        while 1:
            # self.logger.info("[Modbus] Checking devices status now")
            # Collect status of device after an interval of time
            ## Calculate the period and checking point in every term of period
            check_status_speed = MODBUS_READING_SLEEP_TIME
            check_status_point = check_status_speed // 6
            ## Calculate the amount of failed data collecting attempt to set status of device to disconnected
            allow_fails_no = MODBUS_STATUS_TIMEOUT // check_status_speed
            for time_count in range(check_status_speed):
                # Check status of devices when timer reaches to 30 seconds
                if time_count == check_status_point:
                    # Check all the devices in the modbus devices controlling list
                    for device in self.devices_in_control:
                        try:
                            device_source_id = device[DV__SC_ID]
                            slave_id = device[DV__MB_SV_ID]
                            channel_id = device[DV__CHN_ID]
                            dv_type = device[DV__TYPE]
                            direction = device[DV__DIRECTION]
                            if device_source_id in self.status_list:
                                pos = 0
                                # Get position for GMW83DRP device
                                if dv_type == 'gmw83drp-sensor':
                                    for query_pos in range(3):
                                        gmw83_coil = self.status_list [device_source_id][query_pos]
                                        checking_slaveId = gmw83_coil["slave_id"]
                                        checking_chnId = gmw83_coil["channel_id"]
                                        # Get the position of coil in status list
                                        if (slave_id == checking_slaveId and channel_id == checking_chnId):
                                            pos = query_pos
                                # Query data to define device
                                cur_recv = self.status_list[device_source_id][pos]['current_recv']
                                fail_num = self.status_list[device_source_id][pos]['fail_no']
                                status_change = False
                                db_device = devices(sourceid=device_source_id, slaveid=slave_id, channelid=channel_id, logger=self.logger)
                                # Update status based on current received status and fail to receive data times number
                                if cur_recv == True:
                                    fail_num = 0
                                    if db_device.status == 2:
                                        status_change = True
                                    db_device.status = 1
                                else:
                                    fail_num += 1
                                    if (fail_num >= allow_fails_no) or (direction == 1):
                                        if db_device.status == 1:
                                            status_change = True
                                        db_device.status = 2
                                # Reset current_recv for the next checking
                                current_recv = False
                                self.status_list[device_source_id][pos]["current_recv"] = current_recv
                                self.status_list[device_source_id][pos]["fail_no"] = fail_num
                                # Save current status to database - devices table
                                if status_change:
                                    db_device.save()
                            time.sleep(0.001)
                        except Exception as err:
                            self.logger.error("[Modbus] Not able to update current modbus devices status, error: " + str(err))
                time.sleep(1)

    ####################################################################################################
    #[Function]: Maintaining the output value as requested
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #[Return]: N/A
    ####################################################################################################
    def keep_output_value(self):
        self.logger.info("[Modbus] Maintaining output value Operator initiated")
        time.sleep(40)
        while 1:
            for time_count in range(MODBUS_KEEPING_OUTPUT_TIME):
                temp_output_list = {}
                if time_count >= MODBUS_KEEPING_OUTPUT_TIME:
                    self.logger.info("[Modbus] Recovering Digital Output value now")
                time.sleep(1)
                # Check all the devices in the modbus devices controlling list
                # self.logger.debug("[Modbus] Output channels are " + str(self.output_channels))
                if len(self.output_channels) != 0:
                    for channel in self.output_channels:
                        # Prepare indentification information for the channel
                        device_source_id = channel[DV__SC_ID]
                        slave_id = channel[DV__MB_SV_ID]
                        channel_id = channel[DV__CHN_ID]
                        previous_value = CONTROL_OFF
                        if device_source_id in self.previous_outputs.keys():
                            previous_value = self.previous_outputs[device_source_id]
                        # Determine instant control request
                        is_instant = False
                        # Skip this channel if channel address is out of configured range
                        if (int(channel_id) < 21):
                            continue
                        # Process to cover the output value
                        try:
                            # Get the current requested output value of the channel
                            value_to_set = CONTROL_OFF
                            data_from_database = data(sourceid=device_source_id, slaveid=slave_id, channelid=channel_id, logger=self.logger)
                            if hasattr(data_from_database, "data_dev") and data_from_database.data_dev.isnumeric():
                                if int(data_from_database.data_dev) >= (CONTROL_ON + 2):
                                    data_from_database.data_dev = int(data_from_database.data_dev) - 2
                                    data_from_database.save()
                                    is_instant = True
                                value_to_set = int(data_from_database.data_dev)
                            if (previous_value != CONTROL_ON and previous_value != CONTROL_OFF):
                                previous_value = value_to_set
                            # Execute control command if it reaches the period or it is instant control request
                            if (is_instant or previous_value != value_to_set or time_count >= (MODBUS_KEEPING_OUTPUT_TIME - 1)) and (value_to_set == CONTROL_ON or value_to_set == CONTROL_OFF):
                                # Preparing command message to make output request
                                command_message = channel
                                command_message += (value_to_set, )
                                # Send request to set coil value
                                self.write_data(command_message)
                                # Print log on maintaining output
                                maintaining_log = '[Modbus] Maintaining output on ' + str(device_source_id) + ' at status '
                                if value_to_set == CONTROL_ON:
                                    maintaining_log += "ON"
                                elif value_to_set == CONTROL_OFF:
                                    maintaining_log += "OFF"
                                self.logger.debug(maintaining_log)
                            temp_output_list[device_source_id] = value_to_set
                        except Exception as do_err:
                            # If exception occurs, add error log and note process reading fail to repeat reading request later
                            self.logger.error('[Modbus] Failed to maintain output value')
                        # Delay between everytime command an output channel
                        time.sleep(0.001)
                self.previous_outputs = temp_output_list
                # Delay between loop in case output channels list is empty
                time.sleep(0.001)

    ####################################################################################################
    #[Function]: Operate the object of modbusCommunicator
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {modbusCommunicator} - object of class modbusCommunicator
    #[Return]: N/A
    ####################################################################################################
    def run(self):
        self.status_watcher.start()
        self.output_channel_keeper.start()
        self.collect_data()