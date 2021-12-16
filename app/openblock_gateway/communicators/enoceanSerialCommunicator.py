import serial
import copy
import time
import threading
import logging
import sys
import crc8
from threading import Thread
from constant import *
from configuration import *
from .enoceanConverterInterface import *
from .enoceanSwcOperator import *
from .localstorage.database_interface import local_storage
from .localstorage.DevicesModel import devices
from .localstorage.DataModel import data
from ..utils.function_library import *

class enoceanCommunicator(Thread):
    # EnOcean Communicator base-class.
    ser = None

    ####################################################################################################
    #[Function]: Initiate serial port
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #   ttyPath {str} - Path to the ttySXXX file
    #   baudrate {int} - Baud rate of the serial port
    #   logger {logging} - Logging module
    #[Return]: N/A
    ####################################################################################################
    def __init__(self, ttyPath, baudrate, logger):
        # Init instance
        self.logger = logger
        self.logger.info('[EnOcean] Initiation: Configuring enocean serial port')
        super(enoceanCommunicator, self).__init__()
        self.eno_path = ttyPath
        self.eno_baudrate = baudrate
        # Create connection on the enocean serial port
        eno_result = self.establish_eno_comm()
        self.logger.info(eno_result)
        # Create a list to hold the devices that this gateway manages
        self.devices_in_control = []
        self.out_controlled_devices = {}
        self.previous_outputs = {}
        # Create a thread to watch the change of devices status
        self.status_list = {}
        self.status_watcher = threading.Thread(name='check_status', target=self.check_status, args=())
        # Create a thread to maintain output value of output devices
        self.is_handling_control = False
        self.output_channel_keeper = threading.Thread(name='keeping_output', target=self.keep_output_value, args=())
        # Create a thread to maintain output value of output devices
        self.data_listener_pausing = False
        self.data_listener = threading.Thread(name='listen_data', target=self.listen_read, args=())

    ####################################################################################################
    #[Function]: Establishing Enocean serial Communication
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #[Return]: N/A
    ####################################################################################################
    def establish_eno_comm(self):
        result = ""
        self.ser = None
        # Create connection on the enocean serial port
        try:
            self.ser = serial.Serial(self.eno_path)
            if self.ser.is_open:
                result = "[EnOcean] Serial port " + self.ser.name + " is enabled"
            else:
                result = "[EnOcean] Serial port " + self.ser.name + " is not enabled"
        except Exception as err:
            result = "[EnOcean] Serial port " + self.eno_path + " is not valid, error: " + str(err)
            self.ser = serial.Serial()
        self.ser.baudrate = self.eno_baudrate
        return result

    ####################################################################################################
    #[Function]: Parse the request message from cloud and execute writing to output device
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #   req_message {str} - message for sending
    #   is_new_req {bool} - distinguish between processing new control request and maintaining status
    #[Return]: N/A
    ####################################################################################################
    def handle_writing_request(self, req_message={}, is_new_req=False):
        # self.logger.debug('[EnOcean] Handle_writing_request: Initiating sending data')
        # Collect data from database
        if len(req_message) != 0:
            # Check all the devices in the eno devices controlling list
            for swc_dev_id in req_message.keys():
                # Operate the output channels of SWC device
                try:
                    # Calculate the control value to put in the message
                    out_val = self.make_out_value(swc_dev_id, req_message[swc_dev_id], is_new_req)
                    # Execute command to controller
                    device_id = convert_str2hex(swc_dev_id, 4, self.logger)
                    self.request_control(device_id, out_val)
                except Exception as ctl_err:
                    self.logger.error('[EnOcean] Failed to get HEX value to set to controlled devices, error: ' + str(ctl_err))
                    continue
                time.sleep(0.001)

    ####################################################################################################
    #[Function]: Calculate the byte of output channel in the onoff demand message
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #   dev_id {list} - list of byte of device id of the SWC device
    #   channels_info {str} - info data of the channels
    #   is_new_req {bool} - determine new request to refer to origin status of channels
    #[Return]: N/A
    ####################################################################################################
    def make_out_value(self, dev_id, channels_info, is_new_req):
        out_val = 0x00
        # Check the original status of channels if this is new control request from cloud
        if is_new_req:
            try:
                # Collect previous status from data base
                db_data = data(devid=dev_id, logger=self.logger)
                origin_list = db_data.get_data()
                # Combine the value of each channel into one byte data
                for origin in origin_list:
                    # Prepare information for the channel
                    channel = origin[DT__CHN_ID]
                    origin_value = CONTROL_OFF
                    if (origin[DT__DATA] != ""):
                        origin_value = int(origin[DT__DATA])
                    # Get mask based on channel and value to set
                    mask = get_byte_mask(channel, origin_value)
                    # Apply the mask
                    out_val = apply_mask(out_val, mask, origin_value)
            except Exception as ori_err:
                self.logger.error('[EnOcean] Failed to get original status of controlled devices, error: ' + str(ori_err))
            time.sleep(0.0001)
        # Calculate the new output status on output channels into one byte data
        for device in channels_info:
            # Prepare information for the channel
            source_id = device[DV__SC_ID]
            channel = device[DV__CHN_ID]
            # Assign the value needs to be set, if missing field then skip this device
            if len(device) == (DV__EX_PRT_1 + 1):
                value_to_set = int(device[DV__EX_PRT_1])
            else:
                continue
            # Process to calculate the output value depending on channel status
            try:
                # Get mask based on channel and value to set
                mask = get_byte_mask(channel, value_to_set)
                # Apply the mask
                out_val = apply_mask(out_val, mask, value_to_set)
            except Exception as req_err:
                continue
            time.sleep(0.0001)
        return out_val

    ####################################################################################################
    #[Function]: Operate the output on the SWC channels
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #   device_id {str} - device id of the SWC device
    #   output_value {str} - message for sending
    #[Return]: N/A
    ####################################################################################################
    def request_control(self, device_id, output_value):
        # Unlock the SWC device
        # self.logger.debug("[EnOcean] Unlock ERT-SWC device, id: " + str(device_id))
        # Conduct the control message
        unlock_msg = unlock_command(device_id, logger=self.logger)
        # Send unlock message to the SWC device
        try:
            self.write_serial_data(unlock_msg)
        except Exception as ulk_err:
            self.logger.info('[EnOcean] Sending unlock request failed, error: ' + str(ulk_err))
            return False
        time.sleep(1)
        # Conduct the control message
        # self.logger.debug("[EnOcean] Set output control to ERT-SWC device, id: " + str(device_id))
        onoff_msg = onoff_command(device_id, output_value, logger=self.logger)
        # Send Command to turn ON/OFF channels
        try:
            self.write_serial_data(onoff_msg)
            return True
        except Exception as ctl_err:
            self.logger.info('[EnOcean] Sending on/off request failed, error: ' + str(ctl_err))
            return False

    ####################################################################################################
    #[Function]: Request for the status of the SWC channels
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #   device_id {str} - device id of the SWC device
    #[Return]: N/A
    #---------------------------------------------------------------------------------------------------
    #[Currently not used][Reason: function not confirmed]
    ####################################################################################################
    def request_status(self, device_id):
        # Unlock the SWC device
        # self.logger.debug("[EnOcean] Unlock ERT-SWC device, id: " + str(device_id))
        # Conduct the control message
        unlock_msg = unlock_command(device_id, logger=self.logger)
        # Send unlock message to the SWC device
        try:
            self.write_serial_data(unlock_msg)
        except Exception as ulk_err:
            self.logger.info('[EnOcean] Sending on/off request failed, error: ' + str(ulk_err))
            return False
        time.sleep(0.5)
        # Conduct the control message
        # self.logger.debug("[EnOcean] Set output to ERT-SWC device, id: " + str(device_id))
        sts_msg = get_sts_command(device_id, logger=self.logger)
        # Send Command to turn ON/OFF channels
        try:
            self.write_serial_data(sts_msg)
            return True
        except Exception as ctl_err:
            self.logger.info('[EnOcean] Sending on/off request failed, error: ' + str(ctl_err))
            return False

    ####################################################################################################
    #[Function]: Write data to serial port
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #   input_data {str} - message for sending
    #[Return]: N/A
    ####################################################################################################
    def write_serial_data(self, send_data):
        # self.logger.info('[EnOcean]write_serial_data: Begin sending data')
        # Exit if EnOcean communication is not available
        if self.ser == None:
            self.logger.info('[EnOcean] Function write_serial_data: Exit function as Enocean connection not available')
            return False
        # Send the message
        try:
            cat_data = ''
            for byte in send_data:
                cat_data += '{0:0{1}X}'.format(byte, 2)
            # self.logger.debug('[Enocean] Send request with send_data = ' + str(cat_data))
            # Send control value
            self.ser.write(send_data)
        except Exception as err:
            self.logger.error('[EnOcean] Failed to execute write_serial_data, error: ' + str(err))

    ####################################################################################################
    #[Function]: Connect and read data from serial port
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #[Return]: N/A
    ####################################################################################################
    def listen_read(self):
        # Listen to serial port
        while 1:
            # Validate to read only when serial comm is functioning normally
            if isinstance(self.ser, serial.Serial):
                if self.ser.is_open and not self.data_listener_pausing:
                    # Read from serial port if there is received data
                    self.read_serial_data()
            time.sleep(0.001)

    ####################################################################################################
    #[Function]: Read data from serial port
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #[Return]:
    #   list_bytes {list} - List of received data bytes
    ####################################################################################################
    def read_serial_data(self):
        # self.logger.info('[Start]read_serial_data: Start reading data')
        global byte_count
        list_bytes = []
        temp_frame = {
            "data": [],
            "length": 0
        }
        recv_data = b''
        # When getting data at buffer, start to read
        try:
            while self.ser.inWaiting() > 0:
                # Read the data received via serial port
                recv_data = self.ser.read()
                # Check if the sync byte (first byte of the frame) is not 0x55, then eject this data frame
                if (byte_count == 0) and (str('{0:0{1}X}'.format(ord(recv_data), 2)) != '55'):
                    time.sleep(0.001)
                    break
                # Collect the received data into one list
                # End of the old frame, if next byte is 0x55 then continue to read data
                if str('{0:0{1}X}'.format(ord(recv_data), 2)) == '55':
                    byte_count = 0
                    # End of the data frame
                    list_bytes.append(temp_frame['data'])
                    temp_frame = {
                        "data": [],
                        "length": 0
                    }
                # Increase byte_count
                byte_count += 1
                # Collect the received data into one list
                temp_frame['data'].append(recv_data)
                #   operating = False
                time.sleep(0.001)
        except Exception as err:
            self.logger.error("[EnOcean] Failed to collect current enocean devices data, error: " + str(err))
        # If nothing else in buffer, push current read data into list_bytes
        if self.ser.inWaiting() == 0:
            # End of the data frame
            list_bytes.append(temp_frame['data'])
            temp_frame = {
                "data": [],
                "length": 0
            }
        # Store received data to database if any
        if len(list_bytes) != 0:
            byte_count = 0
            # Converse hex data into visualizable
            for frame in list_bytes:
                time.sleep(0.001)
                if validate_data(frame, self.logger):
                    # try:
                        raw_data = 0x00
                        cat_data = ''
                        for byte in frame:
                            raw_data = ord(byte)
                            cat_data += '{0:0{1}X}'.format(raw_data, 2)
                        self.logger.debug("[EnOcean] Received data from other device, full frame = " + str(cat_data))
                        # Analyze the data frame to get device ID and data
                        parsed_data = parse_raw_data(frame)
                        self.logger.debug("[EnOcean] Converting - parsed_data = " + str(parsed_data))
                        # Query device from DB via device ID
                        device_id = str(parsed_data["id"]).upper()
                        if device_id == "NONVALID":
                            self.logger.info("[EnOcean] Received data from EnOcean device but out of scope")
                            continue
                        device_query = devices(devid=device_id, channelid='NULL', protocol=ENOCEAN_PROTOCOL, logger=self.logger)
                        # Query to check if this device found is in list of control
                        device_info = device_query.get_data()
                        if len(device_info) != 0:
                            device_source_id = device_info[0][DV__SC_ID]
                            device_type = device_info[0][DV__TYPE]
                            co2_hex = device_info[0][DV__CO2_HEX]
                            co2_dec = device_info[0][DV__CO2_DEC]
                            co2_sup = device_info[0][DV__CO2_SUP]
                            co2_result = 0
                            # If query data on this devid successfully from DB then store its value to data table in DB
                            if device_type != "":
                                # Modify the format of value according to device type
                                value = ""
                                if device_type == "ert-swc-sensor":
                                    value += parsed_data['values']
                                    if value != "0650" and value != "0652":
                                        continue
                                else:
                                    if device_type == "co2-928-sensor":
                                        value += parsed_data['values']
                                        co2_raw = parsed_data['values'][2:4]
                                        co2_raw = hex_2_dec(co2_raw, self.logger)
                                        co2_hex = hex_2_dec(co2_hex, self.logger)
                                        co2_result = calculate_co2(co2_raw, co2_hex, co2_dec, co2_sup, self.logger)
                                    elif device_type == "etb-sic-p-sensor":
                                        # Verify if the frame is for updating contacting status
                                        precheck = parsed_data['values'][:4]
                                        if precheck == "0000":
                                            # Get the value determine contacting status
                                            value += parsed_data['values'][4:]
                                    # Query the data row and store it to database
                                    data_to_put_database = data(sourceid=device_source_id, devid=device_id, devdata=value, co2value=co2_result, logger=self.logger)
                                    data_to_put_database.save()
                                # Save status to database
                                device_query.status = 1
                                device_query.save()
                                # Confirm that received data from this device to support status updating process
                                if (device_source_id in self.status_list) and ('current_recv' in self.status_list[device_source_id]):
                                    self.status_list[device_source_id]['current_recv'] = True
                    # except Exception as upd_vl_err:
                        # self.logger.error("[EnOcean] Failed to handle received message , error: " + str(upd_vl_err))

    ####################################################################################################
    #[Function]: Collect all EnOcean devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
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
        except Exception as eno_dev_err:
            self.logger.error("[EnOcean] Failed to update EnOcean devices list, errors: " + str(eno_dev_err))

    ####################################################################################################
    #[Function]: Update list of EnOcean sensor devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #[Return]: N/A
    ####################################################################################################
    def update_sensor_list(self):
        # Update list of managed devices
        eno_devices = devices(protocol=ENOCEAN_PROTOCOL, direction=2, logger=self.logger)
        self.devices_in_control = eno_devices.get_data()
        # self.logger.debug("[EnOcean] Current managed sensor devives list is " + str(self.devices_in_control))
        self.update_sensor_status_list()

    ####################################################################################################
    #[Function]: Update sensors status managing list
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
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
                    is_key_in_devlist = False
                    for managed_device in self.devices_in_control:
                        dev_source_id = managed_device[DV__SC_ID]
                        if key == dev_source_id:
                            is_key_in_devlist = True
                    if is_key_in_devlist == True:
                        updated_list[key] = self.status_list[key]
                    time.sleep(0.001)
                # Loop to add device in managed devices list to status controlling list
                for managed_device in self.devices_in_control:
                    # Check if this device does not exist in status controlling list then add it
                    dev_source_id = managed_device[DV__SC_ID]
                    if not (dev_source_id in updated_list):
                        updated_list[dev_source_id] = {
                            "current_recv": False,
                            "fail_no": 2
                        }
                    time.sleep(0.001)
                # Update latest status to self.status_list
                self.status_list = updated_list
                self.logger.info("[EnOcean] Current devices status list is " + str(self.status_list))
            except Exception as err:
                self.logger.error("[EnOcean] Not able to collect current enocean devices, error: " + str(err))

    ####################################################################################################
    #[Function]: Update list of EnOcean output controlled devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #[Return]: N/A
    ####################################################################################################
    def update_output_dev_list(self):
        # Query database to get controlled EnOcean output devices
        eno_controlled_devices = devices(protocol=ENOCEAN_PROTOCOL, direction=1, logger=self.logger)
        temp_out_list = eno_controlled_devices.get_data()
        control_devs = {}
        # Sort devices by device ID
        for device in temp_out_list:
            # Prepare indentification information for the channel
            device_id = device[DV__EN_DV_ID]
            channel = device[DV__CHN_ID]
            # Skip this device if channel is out of configured range
            if (channel == 'NULL') or (int(channel) > 4):
                continue
            try:
                # If device id of SWC not exist in current device insert an element in the dictionary of control devices
                if device_id not in control_devs.keys():
                    control_devs[device_id] = []
                # Push the device item into the list of devices connected to SWC channels
                control_devs[device_id].append(device)
            except Exception as do_err:
                # If exception occurs, add error log and note process reading fail to repeat reading request later
                self.logger.error('[EnOcean] Failed to update output list')
        self.out_controlled_devices = control_devs
        # self.logger.debug("[EnOcean] Current managed output devives list is " + str(self.out_controlled_devices))

    ####################################################################################################
    #[Function]: Checking connection of Enocean devices periodically
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #[Return]: N/A
    ####################################################################################################
    def check_status(self):
        self.logger.info("[EnOcean] Checking status Operator initiated")
        while 1:
            # self.logger.info("[EnOcean] Checking devices status now")
            # Collect status of device after every 30 seconds
            check_status_speed = ENOCEAN_READING_SLEEP_TIME
            check_status_point = check_status_speed // 6
            for time_count in range(check_status_speed):
                # Check status of devices when timer reaches to 30 seconds
                if time_count == check_status_point:
                    try:
                        # Check all the devices in the eno devices controlling list
                        for device in self.devices_in_control:
                            device_source_id = device[DV__SC_ID]
                            device_id = device[DV__EN_DV_ID]
                            direction = device[DV__DIRECTION]
                            device_type = device[DV__TYPE]
                            connect_timeout = ENOCEAN_STATUS_TIMEOUT
                            allow_fail_no = 3
                            if device_source_id in self.status_list:
                                # Handle Sensors
                                if direction == 2:
                                    cur_recv = self.status_list[device_source_id]['current_recv']
                                    fail_num = self.status_list[device_source_id]['fail_no']
                                    db_device = devices(sourceid=device_source_id, devid=device_id, logger=self.logger)
                                    status_change = False
                                    if device[DV__TYPE] == 'etb-sic-p-sensor':
                                        dev_data = data(sourceid=device_source_id, devid=device_id, logger=self.logger)
                                        if ((dev_data.data_dev != '') or (cur_recv)) and (db_device.status == 2):
                                            db_device.status = 1
                                            db_device.save()
                                    else:
                                        if device_type == "co2-928-sensor":
                                            connect_timeout = CO2_928_TIMEOUT
                                        allow_fail_no = connect_timeout // check_status_speed
                                        # Update status based on current received status and fail to receive data times number
                                        if cur_recv == True:
                                            fail_num = 0
                                            if db_device.status == 2:
                                                status_change = True
                                            db_device.status = 1
                                        else:
                                            fail_num += 1
                                            if fail_num >= allow_fail_no:
                                                if db_device.status == 1:
                                                    status_change = True
                                                db_device.status = 2
                                        # Save current status to database - devices table
                                        if status_change:
                                            db_device.save()
                                    # Reset current_recv for the next checking
                                    current_recv = False
                                    self.status_list[device_source_id] = {
                                        "current_recv": current_recv,
                                        'fail_no': fail_num
                                    }
                            time.sleep(0.001)
                    except Exception as err:
                        self.logger.error("[EnOcean]Not able to update status for enocean device, error: " + str(err))
                time.sleep(1)

    ####################################################################################################
    #[Function]: Try binding USB
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #[Return]: N/A
    ####################################################################################################
    def try_binding_usb(self):
        # Define commands
        unbind_command = "echo -n '1-4.3' > /sys/bus/usb/drivers/usb/unbind"
        bind_command = "echo -n '1-4.3' > /sys/bus/usb/drivers/usb/bind"
        # Pause listening to prevent corruption
        if isinstance(self.ser, serial.Serial):
            while self.ser.is_open and self.ser.inWaiting() > 0:
                time.sleep(0.01)
        self.data_listener_pausing = True
        # Execute the commands, first undind the usb then bind back
        self.logger.debug("[EnOcean] Unbinding USB port, then binding again")
        os.system(unbind_command)
        time.sleep(0.01)
        os.system(bind_command)
        time.sleep(0.05)
        # Resume listening
        self.establish_eno_comm()
        self.data_listener_pausing = False
        time.sleep(1)

    ####################################################################################################
    #[Function]: Maintaining the output value as requested
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #[Return]: N/A
    ####################################################################################################
    def keep_output_value(self):
        self.logger.info("[EnOcean] Maintaining output value Operator initiated")
        time.sleep(40)
        while 1:
            # Wait 60s to start a new process cycle
            for time_count in range(ENOCEAN_KEEPING_OUTPUT_TIME):
                temp_output_list = {}
                is_changed = False
                time.sleep(1)
                if (time_count >= ENOCEAN_KEEPING_OUTPUT_TIME):
                    # Manage the connection with swc modules by retry binding USB port
                    retry_binding_req = False
                    db_devices = devices(devtype="ert-swc-sensor", logger=self.logger)
                    db_devices_list = db_devices.get_data()
                    time.sleep(0.01)
                    # Check if any SWC module lost connection
                    for device in db_devices_list:
                        if device[DV__STATUS] == 2:
                            retry_binding_req = True
                            break
                    time.sleep(0.01)
                    # Try rebinding USB port
                    if retry_binding_req:
                        self.logger.debug("[EnOcean] Lost connection to SWC, retrying binding USB port")
                        try:
                            self.try_binding_usb()
                        except Exception as bind_err:
                            self.logger.error("[EnOcean] Error on binding USB port; " + str(bind_err))
                # Check all the devices in the enocean devices controlling list
                instant_list = {}
                # self.logger.debug("[EnOcean] Output channels are " + str(self.out_controlled_devices))
                if len(self.out_controlled_devices) != 0:
                    out_list = copy.deepcopy(self.out_controlled_devices)
                    # Check all the devices in the eno devices controlling list
                    # self.logger.debug("[EnOcean] Controlled output devices is: " + str(out_list))
                    for swc in out_list.keys():
                        is_instant = False
                        # Update status of ERT-SWC-RM device
                        try:
                            devid_bytes = convert_str2hex(swc, 4, self.logger)
                            self.request_status(devid_bytes)
                            time.sleep(1)
                        except Exception as getsts_err:
                            self.logger.error("[EnOcean] Failed to update status of ERT-SWC-RM device, error: " + str(getsts_err))
                        # Handle control output channels
                        for pos in range(len(out_list[swc])):
                            device = out_list[swc][pos]
                            # Prepare indentification information for the channel
                            device_source_id = device[DV__SC_ID]
                            device_id = device[DV__EN_DV_ID]
                            channel_id = device[DV__CHN_ID]
                            previous_value = CONTROL_OFF
                            if device_source_id in self.previous_outputs.keys():
                                previous_value = self.previous_outputs[device_source_id]
                            # Skip this device if channel is out of configured range
                            if (int(channel_id) > 4):
                                continue
                            # Process to cover the output value
                            try:
                                # Get the current requested output value of the channel
                                value_to_set = CONTROL_OFF
                                data_from_database = data(sourceid=device_source_id, devid=device_id, channelid=channel_id, logger=self.logger)
                                data_get = data_from_database.get_data()
                                if hasattr(data_from_database, "data_dev") and data_from_database.data_dev.isnumeric():
                                    if int(data_from_database.data_dev) == (CONTROL_ON + 2):
                                        data_from_database.data_dev = int(data_from_database.data_dev) - 2
                                        data_from_database.save()
                                        is_instant = True
                                    value_to_set = data_from_database.data_dev
                                if  (int(value_to_set) == CONTROL_ON or int(value_to_set) == CONTROL_OFF):
                                    if (previous_value != CONTROL_ON and previous_value != CONTROL_OFF):
                                        previous_value = value_to_set
                                    else:
                                        if previous_value != value_to_set:
                                            is_changed = True
                                    # Preparing command message to make output request
                                    if (len(device) == DV__EX_PRT_1):
                                        out_list[swc][pos] += (value_to_set, )
                                    else:
                                        continue
                                    # self.logger.debug('[EnOcean] Maintaining output on ' + str(device_source_id) + ' at status ' + str(value_to_set))
                                temp_output_list[device_source_id] = value_to_set
                            except Exception as do_err:
                                # If exception occurs, add error log and note process reading fail to repeat reading request later
                                self.logger.error('[EnOcean] Failed to maintain output value, error: ' + str(do_err))
                        if is_instant:
                            instant_list[swc] = out_list[swc]
                        time.sleep(0.0001)
                    # self.logger.debug('[EnOcean] Maintaining outputs are ' + str(out_list))
                    if (len(out_list) != 0) and (is_changed or time_count >= ENOCEAN_KEEPING_OUTPUT_TIME):
                        try:
                            self.logger.info("[EnOcean] Recovering Digital Output value now")
                            self.handle_writing_request(out_list, False)
                        except Exception as err:
                            self.logger.error("[EnOcean] Not able to update output status for enocean controlled devices, error: " + str(err))
                    elif len(instant_list) != 0:
                        try:
                            self.handle_writing_request(instant_list, False)
                        except Exception as err:
                            self.logger.error("[EnOcean] Not able to execute command for enocean controlled devices, error: " + str(err))
                self.previous_outputs = temp_output_list
                # Delay to prevent cascading memory usage when output list is empty
                time.sleep(0.001)

    ####################################################################################################
    #[Function]: Operate the object of enoceanCommunicator
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {enoceanCommunicator} - object of class enoceanCommunicator
    #[Return]: N/A
    ####################################################################################################
    def run(self):
        global byte_count
        byte_count = 0
        # Starting the separated threads
        self.status_watcher.start()
        self.output_channel_keeper.start()
        # Operating a loop to listen for EnOcean data
        self.data_listener.start()
