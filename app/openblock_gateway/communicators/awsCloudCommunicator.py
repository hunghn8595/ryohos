from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import logging
import time
import argparse
import json
import threading
import socket
from pathlib import Path
from threading import Thread
from .localstorage.RoomModel import room
from .localstorage.DevicesModel import devices
from .localstorage.DataModel import data
from .localstorage.database_interface import local_storage
from ..utils.json_interface import to_json, form_json_for_gmw83drp_device
from ..utils.init_module import get_mac_addr
from ..utils.function_library import *
from ..utils.timer_process import event_timer
from datetime import datetime
import os, sys
sys.path.append(os.path.abspath(os.getcwd() + '/openblock_gateway/utils/'))
from constant import *
from configuration import *

class AWSIotThing(Thread):

    ####################################################################################################
    #[Function]: Initiate AWS handling module
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #   mac_address {str} - MAC address of the eth0 interface
    #   reboot_limit {int} - reboot limit that only allow rebooting after passing this limit timestamp
    #   logger {logging} - logging module
    #[Return]: N/A
    ####################################################################################################
    def __init__(self, mac_address, reboot_limit, logger):
        self.logger = logger
        self.logger.info ("[Cloud] Initiating cloud connection")
        super(AWSIotThing, self).__init__()
        # Get MAC address and AWS Thing name
        self.MAC_ADDR = mac_address
        self.AWS_THING_NAME = "GW-" + mac_address.replace(":", "")
        self.REBOOT_LIMIT = reboot_limit
        # Update certificate path
        try:
            self.update_cert_path()
        except Exception as cert_files_err:
            self.logger.error("[Cloud] Failed to query certificate files, error: " + str(cert_files_err))
        # Initiate the AWS cloud connection
        try:
            self.myAWSIoTMQTTClient = AWSIoTMQTTClient(self.AWS_THING_NAME)
            self.myAWSIoTMQTTClient.configureEndpoint(AWS_ENDPOINT, AWS_PORT)
            self.myAWSIoTMQTTClient.configureCredentials(ROOTCA_NAME, PRIVATE_KEY_NAME, CERTIFICATE_NAME)
            self.myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
            self.myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
            self.myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
            self.myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
            self.myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
        except Exception as cfg_aws_err:
            self.logger.error("[Cloud] Failed to configure AWS IoT MQTT client, error: " + str(cfg_aws_err))
        # Define flag of some operations
        self.is_updating_device = False
        # Make thread to check internet
        self.internet_checking = threading.Thread(name='internet_check', target=self.check_connection_status, args=())
        # Make thread to publish data of devices by event trigger
        self.data_publish_trigger = threading.Event()
        self.data_publish_operater = threading.Thread(name='publish_data', target=self.wait_publish_data, args=(self.data_publish_trigger, 10))
        # Make thread to publish status of devices by event trigger
        self.status_publish_trigger = threading.Event()
        self.status_publish_operater = threading.Thread(name='publish_status', target=self.wait_publish_status, args=(self.status_publish_trigger, 10))
        # Create a timestamp, for referrence to avoid duplicated record in a minute
        dateTimeObj = datetime.now()
        self.backup_dt_timestamp = dateTimeObj.strftime("%Y-%b-%d %H:%M")
        self.backup_st_timestamp = dateTimeObj.strftime("%Y-%b-%d %H:%M")
        self.last_connected = int(dateTimeObj.strftime("%s"))
        # Try to connect to cloud
        make_async_loop(self.connect_to_cloud, {})

    ####################################################################################################
    #[Function]: Try to connect to AWS cloud
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #   callback_function {str} - callback function that would call this connect_to_cloud function again
    #   argurments {dict} - argurments that needs to be passed, in this case it is empty
    #[Return]: N/A
    ####################################################################################################
    def connect_to_cloud(self, callback_function, argurments={}):
        try:
            self.myAWSIoTMQTTClient.connect(30)
            self.logger.info("[Cloud] Connected to cloud")
        except Exception as err:
            # self.logger.error(str(err))
            if type(err) is socket.gaierror:
                self.logger.error("[Cloud] No connection to cloud... ")
            else:
                self.logger.error("[Cloud] Certificates expired or wrong certificates")
            # Retry connecting to cloud on a new thread
            if callable(callback_function):
                time.sleep(SLEEP_TIME_OF_RETRYING_CONNECT)
                self.logger.error("[Cloud] Retrying to connect to cloud... ")
                callback_function(self.connect_to_cloud, {})

    ####################################################################################################
    #[Function]: Combine and update the paths of certificates into AWS module
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #[Return]: N/A
    ####################################################################################################
    def update_cert_path(self):
        global CERT_PATH
        global CERTIFICATE_NAME
        global ROOTCA_NAME
        global PRIVATE_KEY_NAME
        # Function update file name
        def get_current_name(folder_obj, file_suffix, origin):
            temp_result = list(folder_obj.glob(file_suffix))
            if len(temp_result) != 0:
                return './' + str(temp_result[0])
            # If no result found, return empty
            return origin
        # Get folder containing certificates
        cert_folder = Path(CERT_PATH)
        # Get the certificate file directory
        CERTIFICATE_NAME = get_current_name(cert_folder, '*certificate.pem.crt', CERTIFICATE_NAME)
        # Get the private key file directory
        PRIVATE_KEY_NAME = get_current_name(cert_folder, '*private.pem.key', PRIVATE_KEY_NAME)
        # Get the Amazon Root CA file directory
        ROOTCA_NAME = get_current_name(cert_folder, '*AmazonRootCA1.pem', ROOTCA_NAME)

    # Connect and subscribe to AWS IoT

    ####################################################################################################
    #[Function]: Handle get the valid certificates when current ones are out of order
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #[Return]: N/A
    ####################################################################################################
    def update_valid_cert(self):
        # self.logger.debug ("[Cloud] TODO: Handle to get valid certificate")
        time.sleep(10)
        self.logger.debug("[Cloud] End handling to get valid certificate")

    ####################################################################################################
    #[Function]: Check status of internet
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #[Return]: N/A
    ####################################################################################################
    def check_connection_status(self):
        connection_status = "disconnected"
        checking_result = False
        while(1):
            # Get timestamp for reboot
            dateTimeObj = datetime.now()
            current_time = int(dateTimeObj.strftime("%s"))
            # Update status of internet connection
            try:
                checking_result = check_connection()
            except Exception as err:
                pass
            # Handle internet connection status
            if checking_result:
                if connection_status == "disconnected":
                    # Print log of internet connection
                    self.logger.info("[Cloud] Getting connection to internet")
                connection_status = "connected"
                # Renew last_connected, not meaning internet is disconnected
                self.last_connected = current_time
            else:
                # Change status
                if connection_status == "connected":
                    # Print log of internet disconnection
                    self.logger.error("[Cloud] Lost connection to internet")
                else:
                    # Determine if it passed reboot limit
                    if current_time > self.REBOOT_LIMIT and ((current_time - self.last_connected) >= (REBOOT_SHORT_DELAY * 60)):
                        self.logger.info("[Cloud] Cannot get connected - going to reboot system")
                        # Write the above timestamp into storing file
                        remove_file(REBOOT_TRACKFILE)
                        write_to_file(REBOOT_TRACKFILE, str(current_time))
                        # Set schedule for rebooting
                        os.system("reboot")
                connection_status = "disconnected"
            time.sleep(20)

    ####################################################################################################
    #[Function]: Initiate a timer to publish data every minute
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #[Return]: N/A
    ####################################################################################################
    def wait_publish_data(self, event, timeout):
        data_publish_timer = event_timer(event, DATA_PUBLISH_PERIOD, self.logger)
        topic = AWS_TOPIC_PREFIX + self.AWS_THING_NAME + AWS_DATA_PUBLISH_TOPIC_STAGE
        while 1:
            # time.sleep(0.0001)
            event_is_set = event.wait(timeout)
            if event_is_set:
                # Handle to collect data of devices and publish to cloud if triggered
                self.publish_topic_thread(topic)
            else:
                # Handle timeout if any process is needed
                pass
            event.clear()

    ####################################################################################################
    #[Function]: Collect and publish data of devices to cloud
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #   topic {str} - AWS topic where update the data information of the devices
    #[Return]: N/A
    ####################################################################################################
    def publish_topic_thread(self, topic):
        # self.logger.debug("[Cloud] Publish to cloud to /streams")
        # Prepare timestamp
        dateTimeObj = datetime.now()
        timestampStr = dateTimeObj.strftime("%Y-%b-%d %H:%M:%S.%f")
        previous_timestamp = self.backup_dt_timestamp
        self.backup_dt_timestamp = dateTimeObj.strftime("%Y-%b-%d %H:%M")
        if previous_timestamp == self.backup_dt_timestamp:
            self.logger.info("[Cloud] Duplicate timestamp of data json in a minute " + str(timestampStr))
            return
        # Prepare to query data
        self.db = local_storage(logger=self.logger)
        list_of_rooms = self.db.query_data("rooms")
        # Pause process if devices list is being updated
        wait_flag_changed(self.is_updating_device, False, 5)
        # Collect data by rooms
        for room in list_of_rooms:
            room_id = room[RM__ROOM_ID]
            # self.logger.debug ("[Cloud] Getting data from room : " + str(room_id))
            data_to_query = {'room' : room_id}
            try:
                list_of_devices = self.db.query_data("devices", data_to_query)
                # self.logger.debug ("[Cloud] Sensors in room : " + str(list_of_devices))
                list_of_devices_in_room = []
                if len(list_of_devices) != 0:
                    for device in list_of_devices:
                        # if (device[DV__TYPE] in SENSOR_DEVICES_LIST) and (device[DV__RELATED_SC_ID] == 'NULL') and (device[DV__STATUS] == 1):
                        if (device[DV__TYPE] in SENSOR_DEVICES_LIST) and (device[DV__STATUS] == 1):
                            if device[DV__MB_SV_ID] == 'NULL' :    # EnOcean device data
                                # self.logger.info("[Cloud] Getting data of enocean devices")
                                device_enocean_id = device[DV__EN_DV_ID]
                                data_of_device = data(sourceid=device[DV__SC_ID], logger=self.logger)
                                # self.logger.debug("[Cloud] Getting data from " + device_enocean_id + " : " + data_of_device.data_dev)
                                if data_of_device.data_dev != "":
                                    # Prepare sensor information
                                    sensor_info = {}
                                    sensor_info['source_id'] = device[DV__SC_ID]    # source id of device
                                    sensor_info['deviceId'] = device_enocean_id
                                    sensor_info['type'] = device[DV__TYPE]
                                    sensor_info['data'] = data_of_device.data_dev
                                    if device[DV__TYPE] == "co2-928-sensor":
                                        sensor_info['d_position'] = device[DV__CO2_POS]
                                    # Insert json formatted sensor information into published message
                                    json_info = to_json(sensor_info)
                                    if json_info != {}:
                                        list_of_devices_in_room.append(json_info)
                                    else:
                                        self.logger.error("[Cloud] Failed to convert data of " + str(device[DV__SC_ID]))
                                else:
                                    self.logger.debug("[Cloud] There is no data of " + str(device[DV__SC_ID]) + " in database")
                            elif device[DV__EN_DV_ID] == 'NULL' :  # Modbus device data
                                # self.logger.info("[Cloud] Getting data of modbus devices")
                                slaveId = device[DV__MB_SV_ID]
                                channelAddressId = device[DV__CHN_ID]
                                data_of_device = data(sourceid=device[DV__SC_ID], slaveid=slaveId, channelid=channelAddressId, logger=self.logger)
                                # self.logger.debug("[Cloud] Getting data from " + str(device[DV__SC_ID]) + " at coil - " + channelAddressId + " : " + data_of_device.data_dev)
                                if data_of_device.data_dev != "":
                                    # Prepare sensor information
                                    sensor_info  = {}
                                    sensor_info['source_id'] = device[DV__SC_ID]
                                    sensor_info['slaveId'] = slaveId
                                    sensor_info['channelAddressId'] = channelAddressId
                                    sensor_info['type'] = device[DV__TYPE]
                                    if device[DV__TYPE] == "gmd20-sensor" or device[DV__TYPE] == "gmw83drp-sensor":
                                        sensor_info['d_position'] = device[DV__CO2_POS]
                                    if device[DV__TYPE] == "gmw83drp-sensor":
                                        sensor_info['v_type'] = device[DV__VAL_TYPE]
                                    sensor_info['data'] = data_of_device.data_dev
                                    # Insert json formatted sensor information into published message
                                    json_info = to_json(sensor_info)
                                    if json_info != {}:
                                        list_of_devices_in_room.append(json_info)
                                    else:
                                        self.logger.error("[Cloud] Failed to convert data of " + str(device[DV__SC_ID]))
                                else:
                                    self.logger.debug("[Cloud] There is no data of " + str(device[DV__SC_ID]) + " in database")
                if len(list_of_devices_in_room) != 0:
                    json_publish = {}
                    json_publish["gateway"] = {}
                    json_publish["gateway"]["source_id"] = self.AWS_THING_NAME
                    json_publish["gateway"]["type"] = "openblocks-iot-vx2"
                    json_publish['room_id'] = room_id
                    json_publish['timestamp'] = timestampStr
                    list_of_devices_in_room = form_json_for_gmw83drp_device(list_of_devices_in_room)
                    json_publish['data'] = list_of_devices_in_room
                    json_publish = json.dumps(json_publish)
                    self.logger.info("[Cloud] Publishing for room " + str(room_id))
                    # Create a asynchronous process
                    input_arguments = {
                        "title": "Data",
                        "topic": topic,
                        "json": json_publish,
                        "attempts_no": 0,
                        "attempts_limit": NUMBER_OF_RETRY_PUBLISHING
                    }
                    # Start process operating publishing data to cloud
                    make_async_loop(self.publish_asynchronous, input_arguments)
                else:
                    self.logger.debug("[Cloud] There is no data to publish for room " + str(room_id))
            except Exception as err:
                self.logger.error("[Cloud] Failed to collect data and publish streaming message belong to room " + str(room[RM__ROOM_ID]))
            time.sleep(0.0001)
        self.db.close()

    ####################################################################################################
    #[Function]: Initiate a timer to publish status every minute
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #[Return]: N/A
    ####################################################################################################
    def wait_publish_status(self, event, timeout):
        status_publish_timer = event_timer(event, STATUS_PUBLISH_PERIOD, self.logger)
        topic = AWS_TOPIC_PREFIX + self.AWS_THING_NAME + AWS_STATUS_PUBLISH_TOPIC_STAGE
        while 1:
            # time.sleep(0.0001)
            event_is_set = event.wait(timeout)
            if event_is_set:
                # Handle to collect status of devices and publish to cloud if triggered
                self.publish_device_status(topic)
            else:
                # Handle timeout if any process is needed
                pass
            event.clear()

    ####################################################################################################
    #[Function]: Collect and publish status of devices to cloud
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #   topic {str} - AWS topic where data would be published
    #[Return]: N/A
    ####################################################################################################
    def publish_device_status(self, topic=''):
        # self.logger.info("[Cloud] Start publishing status")
        # Preparing status_message frame
        dateTimeObj = datetime.now()
        timestampStr = dateTimeObj.strftime("%Y-%b-%d %H:%M:%S.%f")
        previous_timestamp = self.backup_st_timestamp
        self.backup_st_timestamp = dateTimeObj.strftime("%Y-%b-%d %H:%M")
        if previous_timestamp == self.backup_st_timestamp:
            self.logger.info("[Cloud] Duplicate status json timestamp in a minute " + str(timestampStr))
            return
        # The format status message used for publishing
        status_message = {
            "state": {
                "reported": {
                    "gateway": {
                        "mac_address": self.MAC_ADDR
                    },
                    "timestamp": timestampStr,
                    "type": 2,
                    "data": []
                }
            }
        }
        # Pause process if devices list is being updated
        wait_flag_changed(self.is_updating_device, False, 5)
        # Query data of rooms from Database
        try:
            rooms_db = room(logger=self.logger)
            rooms_list = rooms_db.get_data()
            if len(rooms_list) != 0:
                # Collect status data by room, Query data of devices in one room from Database
                for checking_room in rooms_list:
                    # Get room id
                    if checking_room[RM__ROOM_ID] != '':
                        room_id = checking_room[RM__ROOM_ID]
                    else:
                        # If failed to get room id, skip this room
                        continue
                    # Get sensor devices
                    data_of_room = {
                        'room_id': room_id,
                        'devices': [],
                        'control_devices': [],
                    }
                    db_devices = devices(room=room_id, logger=self.logger)
                    db_devices_list = db_devices.get_data()
                    # Filter to get sensors or control trackers
                    sensors_list = []
                    ctl_trackers_list = []
                    for device in db_devices_list:
                        if (device[DV__DIRECTION] == 2):
                            # Filter to get sensor
                            if device[DV__TYPE] not in TRACKING_DEVICES_LIST:
                                sensors_list.append(device)
                            # Filter to get controlled device
                            if (device[DV__RELATED_SC_ID] != 'NULL') or (device[DV__TYPE] in TRACKING_DEVICES_LIST):
                                ctl_trackers_list.append(device)
                    # Make the list of sensor devices active in a room
                    devices_of_room = {}
                    list_of_devices_in_room = []
                    for device in sensors_list:
                        device_source_id = device[DV__SC_ID]
                        # Check collected status, if connected then add this device source id for publishing the status message
                        if (device[DV__STATUS] == 1):
                            devices_of_room[device_source_id] = 1
                    # Push the list of of devices active in this room for publishing status message
                    # self.logger.info([Cloud] devices_of_room)
                    for src_id in devices_of_room.keys():
                        list_of_devices_in_room.append(src_id)
                    data_of_room['devices'] = list_of_devices_in_room
                    time.sleep(0.0001)

                    # Get control devices status
                    list_of_control_devices_in_room = []
                    try:
                        # self.logger.debug("[Cloud] Publishing status, ctl_trackers_list is " + str(ctl_trackers_list))
                        for device in ctl_trackers_list:
                            control_device_status = {
                                'source_id': ''
                            }
                            if device[DV__MB_SV_ID] != 'NULL':
                                db_data = data(sourceid=device[DV__SC_ID], slaveid=device[DV__MB_SV_ID], channelid=device[DV__CHN_ID], logger=self.logger)
                                # Check collected status, if connected then add this device source id for publishing the status message
                                control_device_status['source_id'] = device[DV__SC_ID]
                                control_device_status['status_id'] = CONTROL_OFF
                                try:
                                    if db_data.data_dev != '':
                                        control_device_status['status_id'] = int(db_data.data_dev)
                                except Exception as sensor_stt_err:
                                    self.logger.error("[Cloud] Not able to collect status for controlled devices, error: " + str(sensor_stt_err))
                            elif device[DV__RELATED_SC_ID] != 'NULL':
                                db_data = data(sourceid=device[DV__SC_ID], logger=self.logger)
                                control_device_status['source_id'] = device[DV__RELATED_SC_ID]
                                control_device_status['type'] = device[DV__TYPE]
                                control_device_status['value'] = db_data.data_dev
                                if control_device_status['value'] == "":
                                    control_device_status['value'] = "00"
                                if (control_device_status['value'] != "00") and (device[DV__SC_ID] not in data_of_room['devices']):
                                    data_of_room['devices'].append(device[DV__SC_ID])
                            list_of_control_devices_in_room.append(control_device_status)
                    except Exception as condv_err:
                        self.logger.error("[Cloud] Not able to get controlled devices status, error: " + str(condv_err))
                    data_of_room['control_devices'] = list_of_control_devices_in_room
                    # Add this room status information object in to json data
                    status_message['state']['reported']['data'].append(data_of_room)
                    time.sleep(0.0001)
            # Serialize status_message from type of dict into a JSON formatted string
            status_message_json = json.dumps(status_message)
            if status_message['state']['reported']['data'] != []:
                # Create a asynchronous process
                input_arguments = {
                    "title": "Status",
                    "topic": topic,
                    "json": status_message_json,
                    "attempts_no": 0,
                    "attempts_limit": NUMBER_OF_RETRY_PUBLISHING
                }
                # Start process operating publishing data to cloud
                make_async_loop(self.publish_asynchronous, input_arguments)
        except Exception as err:
            self.logger.error("[Cloud] Not able to publish devices status, error: " + str(err))

    ####################################################################################################
    #[Function]: Collect and publish status of devices to cloud
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #   topic {str} - AWS topic where would be subscribed
    #   callback {func} - callback function that would be call if acknowledge message on the topic
    #[Return]: N/A
    ####################################################################################################
    def subscribe_data(self, topic, callback):
        self.myAWSIoTMQTTClient.subscribe(topic, 1, callback)

    ####################################################################################################
    #[Function]: Collect and publish status of devices to cloud
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #   topic {str} - AWS topic where data would be published
    #   data {str} - message that would be published
    #   default_wait_time {int} - timeout of publish process
    #[Return]: N/A
    ####################################################################################################
    def publish_synchronous(self, topic, data, default_wait_time):
        try :
            self.myAWSIoTMQTTClient.publish(topic, data,1)
            time.sleep(default_wait_time)
        except Exception as err:
            self.logger.error("[Cloud] Failed to publish to cloud, error: " + str(err))

    ####################################################################################################
    #[Function]: Collect and publish status of devices to cloud
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #   callback_function {func} - callback function that would call this publish_asynchronous function again
    #   arguments {dict} - input arguments used by publish_asynchronous and passed through loop times
    #[Return]:
    #   result {bool} - result of publishing
    ####################################################################################################
    def publish_asynchronous(self, callback_function, arguments):
        result = True
        # Get argument for the new async process
        title = arguments['title']
        topic = arguments['topic']
        data = arguments['json']
        try_no = arguments['attempts_no']
        try_limit = arguments['attempts_limit']
        # Dynamic log
        extend_log = ""
        if try_no > 0:
            extend_log = "Retry "
        # Try publishing
        try:
            time.sleep(0.01)
            # Publish data to topic on AWS
            self.logger.info("[Cloud] " + extend_log + "Publishing " + str(title) + " json: " + str(data))
            self.myAWSIoTMQTTClient.publish(topic, data, 1)
            self.logger.info("[Cloud] Completed Publishing " + str(title))
        except Exception as err:
            result = False
            self.logger.error("[Cloud] Failed to publish " + str(title))
            # Retry to publish message, if pass the try attempts limit, escape loop
            if callable(callback_function) and try_no < try_limit:
                arguments['attempts_no'] += 1
                extended_delay = int(arguments['attempts_no'] * 1)
                time.sleep(180 + extended_delay)
                callback_function(self.publish_asynchronous, arguments)
        return result

    ####################################################################################################
    #[Function]: Execute the main threads of AWSIotThing module
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {AWSIotThing} - object of class AWSIotThing
    #[Return]: N/A
    ####################################################################################################
    def run (self):
        # Start the thread in which publish data of devices periodically
        self.data_publish_operater.start()
        # Make delay between 2 threads to reduce performance
        time.sleep(8)
        # Start the thread in which publish status of devices periodically
        self.status_publish_operater.start()
        # Start  the thread in which check internet connection periodically
        self.internet_checking.start()