# Provider for different Communicator -classes.
import os, sys
import serial
import time
import threading
import json
import logging
import csv
import shutil
import fcntl
import copy
from openblock_gateway.utils.init_setting import set_constant_config
set_constant_config()
shutil.move("./configuration.py", "./openblock_gateway/utils/configuration.py")

from openblock_gateway.utils.tracking_support import get_unique_list
from openblock_gateway.utils.init_module import *
from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from openblock_gateway.communicators.enoceanSerialCommunicator import enoceanCommunicator
from openblock_gateway.communicators.modbusSerialCommunicator import modbusCommunicator
from openblock_gateway.communicators.awsCloudCommunicator import AWSIotThing
from openblock_gateway.communicators.outDevicesController import outputController
from openblock_gateway.communicators.localstorage.DevicesModel import devices
from openblock_gateway.communicators.localstorage.RoomModel import room
from openblock_gateway.communicators.localstorage.DataModel import data
from openblock_gateway.communicators.localstorage.database_interface import local_storage
from openblock_gateway.utils.constant import *
from openblock_gateway.utils.configuration import *
from openblock_gateway.utils.timer_process import *
from openblock_gateway.utils.function_library import *
from datetime import datetime
import ast

####################################################################################################
# Execute Main Flow
####################################################################################################
if __name__ == '__main__':
    ### PREPARE INIT PROCESS ###
    # Initiate logging module
    logger = init_logging()
    logger.info("========================================================================================================================================================================================================")
    logger.info("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    logger.info("========================================================================================================================================================================================================")
    logger.info("[Init][Start] Initiating IoT Gateway application")
    # Get the default MAC address of Gateway
    MAC_ADDR = get_mac_addr(DEFAULT_NETWORK_IF, logger)
    AWS_THING_NAME = "GW-" + MAC_ADDR.replace(":", "")
    # Getting response from cloud flag
    get_devices_to_connect = False
    # Check if currently reboot
    REBOOT_LIMIT = check_reboot(logger)
    # Initiate database of Gateway
    init_database(logger)
    # Initiate tracking file
    init_tracking_file(logger)
    # Initiate AWS cloud communicator module
    AWSClient = AWSIotThing(MAC_ADDR, REBOOT_LIMIT, logger)
    # Initiate peripherol devices communicator modules
    ## Initiate EnOcean
    enoCommunicator = enoceanCommunicator(ENO_TTYPATH, ENO_BAUDRATE, logger)
    ## Initiate Modbus
    modbusCommunicator = modbusCommunicator(MODBUS_TTYPATH, MODBUS_BAUDRATE, logger)
    ## Initiate common controller module
    controller = outputController(logger)
    time.sleep(0.005)


    ### DEFINE FUNCTIONS ###
    # Get devices list function
    def add_devices(client, userdata, message):
        global logger
        global room
        global devices
        global data
        global get_devices_to_connect
        logger.info ("[get_devices] Obtained message from AWS topic " + str(AWS_DEVICES_SUBSCRIBE_TOPIC_STAGE))
        # Turn on flag of updating devices in AWSClient to pause some processes
        AWSClient.is_updating_device = True
        data_from_cloud = message.payload.decode('utf-8')
        devices_in_rooms = {'data': []}
        rooms_of_devices = []
        is_on_bootup = not get_devices_to_connect
        try:
            devices_in_rooms = ast.literal_eval(data_from_cloud)
            # Get GW thing name on the cloud
            logger.debug("[get devices] Received data_from_cloud = " + str(devices_in_rooms))
            # Get rooms and devices of rooms on cloud
            rooms_of_devices = devices_in_rooms['data']
            get_devices_to_connect = True
        except Exception as err:
            logger.error('[get_devices] Fail to parse json from cloud, error: ' + str(err))
            return False
        database_connection = local_storage(logger=logger)
        # Get rooms from database
        list_of_rooms, list_room_to_process = get_rooms_on_init_message(database_connection)
        logger.debug ("[get devices] Room list : " + str(list_of_rooms))
        for room_info in rooms_of_devices:
            logger.debug ("[get devices] Room to process : " + str(room_info))
            list_of_devices_to_process_EnOcean, list_of_devices_to_process_Modbus, list_of_devices = get_devices_to_process_on_init_message(database_connection, \
                room, room_info, list_room_to_process, logger)
            devices_to_database = get_devices_to_database_on_init_message(database_connection, room_info, logger)
            # Modify the devices in database to match with the message on cloud
            if set_database_with_devices_on_init_message(room_info, database_connection, data, devices, devices_to_database, \
                list_of_devices_to_process_Modbus, list_of_devices_to_process_EnOcean, logger, list_of_devices, enoCommunicator, modbusCommunicator, is_on_bootup):
                logger.info ("[get devices] Successfully saved devices to database")
            else :
                logger.info ("[get devices] Failed to save to database")
        # Modify database based on Rooms info from cloud
        if set_database_with_rooms_on_init_message(database_connection, data, list_room_to_process, logger, enoCommunicator, modbusCommunicator):
            logger.info ("[get devices] Succesully modified rooms")
        else :
            logger.info ("[get devices] Failed to modify rooms")
        # Add folders to put cameras' image
        update_camera_folders(database_connection, FTP_SERVER_FOLDER_PATH, logger)
        # Turn off flag of updating devices in AWSClient to continue the paused processes
        AWSClient.is_updating_device = False
        database_connection.close()
        # Update list of EnOcean devices into enoCommunicator model
        enoCommunicator.collect_devices()
        # Update list of EnOcean devices into modbusCommunicator model
        modbusCommunicator.collect_devices()
    #[END OF FUNCTION][add_devices]#########################################################################################

    # Get tracking data function
    def get_tracking(client, userdata, message):
        # logger.debug("[data_tracking] Received message from /app-tracking")
        data_from_cloud = message.payload.decode('utf-8')
        message_from_cloud = ast.literal_eval(data_from_cloud)
        # get GW thing name on the cloud
        logger.info("[data_tracking] Received data_from_cloud = " + str(message_from_cloud))
        flag_modified_data = False
        data_tracking = {}
        date_time = ''
        room_name = ''
        infection_rate = {}
        try:
            data_tracking = message_from_cloud['data_tracking']
            date_time = message_from_cloud['time_stamp']
            room_name = message_from_cloud['room_name']
            infection_rate = message_from_cloud['infection_rate']
        except Exception as err:
            logger.error('[data_tracking] Fail to format the tracking file, error: ' + str(err))
        outdoor_co2 = ""
        temperature = ""
        indoor_co2 = ""
        humidity = ""
        if 'out_co2' in data_tracking.keys():
            outdoor_co2 = data_tracking['out_co2']
        if 'temp' in data_tracking.keys():
            temperature = data_tracking['temp']
        if 'in_co2' in data_tracking.keys():
            indoor_co2 = data_tracking['in_co2']
        if 'humidity' in data_tracking.keys():
            humidity = data_tracking['humidity']
        influenza_rate = 0
        tuberculosis_rate = 0
        measles_rate = 0
        covid_rate = 0
        if 'influenza' in infection_rate.keys():
            influenza_rate = infection_rate['influenza']
        if 'tuberculosis' in infection_rate.keys():
            tuberculosis_rate = infection_rate['tuberculosis']
        if 'measles' in infection_rate.keys():
            measles_rate = infection_rate['measles']
        if 'covid' in infection_rate.keys():
            covid_rate = infection_rate['covid']
        # Convert date time update
        try:
            # Try to convert time stamp if it goes in correct format of date time in following case
            try:
                # Format contains shorten month name
                date_time_obj = datetime.strptime(date_time, '%Y-%b-%d %H:%M:%S.%f')
            except Exception as tm_month_err:
                # Format contains full month name
                date_time_obj = datetime.strptime(date_time, '%Y-%B-%d %H:%M:%S.%f')
        except Exception as tm_stm_err:
            # If receive exceptional format of date_time, get the current time stamp from gateway instead
            logger.error ('[data_tracking] Exceptional format of date_time, get the current time stamp, error: ' + str(tm_stm_err))
            date_time_obj = datetime.now()
        date_time = date_time_obj.strftime('%Y/%m/%d %H:%M:%S')
        # Combine tracking data of room into a list
        room_data = [date_time, room_name, outdoor_co2, temperature, humidity, indoor_co2, influenza_rate\
            , tuberculosis_rate, measles_rate, covid_rate]
        # logger.debug("[data_tracking] Saving room : " + str(room_data))
        line_to_overwrite = 0
        data_to_write = []
        # list_of_columns = ['Time', 'Room', 'Co2Out', 'Temperature', 'Humidity', 'Co2In', 'Influenza', 'Tuberculosis', 'Measles', 'Covid']
        number_of_time_to_retry = 5
        with open(TRACKING_FILE, 'r') as b:
            # fcntl.flock(x, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for i in range(0, number_of_time_to_retry):
                try:
                    fcntl.flock(b, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except IOError as e:
                    # raise on unrelated IOErrors
                    if e.errno != errno.EAGAIN:
                        logger.info("[data_tracking] Tracking file is in progress")
                    time.sleep(5)
            reader = csv.reader(b)
            # data_to_write.append(list_of_columns)
            for row in reader:
                try:
                    # logger.debug('[data_tracking] Row in csv : ' + str(row))
                    if row[1] == room_name:
                        flag_modified_data = True
                        data_to_write.append(room_data)
                    else :
                        data_to_write.append(row)
                    line_to_overwrite = line_to_overwrite + 1
                except Exception as err:
                    logger.info('[data_tracking] Reaching the end of file')
            if not flag_modified_data :
                data_to_write.append(room_data)
        with open(TRACKING_FILE, 'w+') as b:
            logger.info('[data_tracking] List of rows to write to csv : ' + str(data_to_write))
            writer = csv.writer(b)
            for data_row in data_to_write:
                writer.writerow(data_row)
            fcntl.flock(b, fcntl.LOCK_UN)
    #[END OF FUNCTION][get_tracking]########################################################################################

    # Handling control request function
    def handle_control_request(client, userdata, message):
        # Accessing global variables
        global logger
        global data
        # logger.debug('[Control_output][Start]handle_control_request')
        is_failed = False
        instant_list = {}
        operated_list = []
        # Convert json to dictionary type
        demand_from_cloud = message.payload.decode('utf-8')
        message_from_cloud = {'data': []}
        try:
            message_from_cloud = ast.literal_eval(demand_from_cloud)
        except Exception as err:
            logger.error('[Control_output] Failed to parse json from cloud, error: ' + str(err))
            return
        logger.debug("[Control_output] Received control request from cloud, message is: " + str(message_from_cloud))
        # Extracting message to get the list of controlled devices
        try:
            list_of_dev, instant_list = make_dev_list_from_control_msg(message_from_cloud, logger)
            # logger.debug("[Control_output] Data from cloud, list of devices is: " + str(list_of_dev))
            # Update information into controller module
            operated_list = controller.update_cloud_req(list_of_dev)
        except Exception as err:
            is_failed = True
        # In case cloud demand an instant control, respond back to Cloud
        response_msg = message_from_cloud
        time.sleep(0.001)
        logger.debug ("[Control_output] output status responded to cloud: " + str(operated_list))
        # Collect the result status of control request handling
        if 'data' in response_msg.keys() and not is_failed and len(operated_list) != 0:
            # In case there and multiple requests for many devices as one time, run loop for every element, currently there would be only one
            for device in response_msg['data']:
                if 'source_id' in device.keys():
                    source_id = device['source_id']
                    # Confirm the final output status value
                    device_info = controller.final_out_control[source_id]['dev_info']
                    if source_id not in operated_list or not get_module_status(device_info):
                        response_msg['data'].remove(device)
            # Delay in all cases
            time.sleep(3)
            if len(instant_list) == 0:
                # Delay longer when respond to auto control
                time.sleep(5)
            # Prepare to publish by converting message, getting the topic to publish response to cloud
            if len(response_msg['data']) != 0:
                # Get current timestamp
                dateTimeObj = datetime.now()
                timestampStr = dateTimeObj.strftime("%Y-%b-%d %H:%M:%S.%f")
                response_msg['time_stamp'] = timestampStr
                # JSON encoding
                response_msg = json.dumps(response_msg)
                # Conduct topic name
                topic = AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_CTL_RESULT_PUBLISH_TOPIC_STAGE
                # Create a asynchronous process
                input_arguments = {
                    "title": "Control_Response",
                    "topic": topic,
                    "json": response_msg,
                    "attempts_no": 0,
                    "attempts_limit": NUMBER_OF_RETRY_PUBLISHING
                }
                # Start process operating publishing data to cloud
                make_async_loop(AWSClient.publish_asynchronous, input_arguments)
                logger.info("[Control_output] Confirming for control, publishing response message " + str(response_msg) + " onto topic " + str(topic))
    #[END OF FUNCTION][handle_control_request]##############################################################################

    # Make a timer to execute sync_ctl function periodically
    def wait_publish_ctl(event, timeout):
        co2_timer = event_timer(event, CONTROL_STEP_DURATION, logger)
        while 1:
            time.sleep(0.0001)
            event_is_set = event.wait(timeout)
            if event_is_set:
                # Operate controlling
                sync_ctl()
            else:
                # Handle timeout if any process is needed
                pass
            event.clear()
    #[END OF FUNCTION][wait_publish_ctl]####################################################################################

    # Synchronyze changes of control by gateway to cloud
    def sync_ctl():
        # logger.info("[Control_output] Check and publish current control status to cloud")
        # Get current time
        dateTimeObj = datetime.now()
        timestampStr = dateTimeObj.strftime("%Y-%b-%d %H:%M:%S.%f")
        # Init message of Gateway
        template_message = {
            "gateway": {
                "source_id": AWS_THING_NAME,
            },
            "room_id": "",
            "timestamp": timestampStr,
            "data": []
        }
        template_device = {
            "source_id": "",
            "type_id": CTL_TYPE_INSTANT,
            "status_id": CONTROL_OFF
        }
        # Get rooms from database
        database_connection = local_storage(logger=logger)
        list_of_rooms = database_connection.query_data("rooms")
        # Checking changings on output devices by each room
        if len(controller.final_out_control) != 0:
            for room in list_of_rooms:
                room_id = room[RM__ROOM_ID]
                # Conduct message for the room
                room_message = copy.deepcopy(template_message)
                room_message['room_id'] = room_id
                # Check change on each device in this room
                for source_id in controller.final_out_control.keys():
                    dev_info = controller.final_out_control[source_id]['dev_info']
                    # Skip devices of other rooms
                    if dev_info[DV__ROOM] != room_id:
                        continue
                    # Get the common control data
                    cloud_control = controller.final_out_control[source_id]['cloud_control']
                    offline_control = controller.final_out_control[source_id]['co2_control']
                    instant_control = controller.final_out_control[source_id]['instant_control']
                    current_status = controller.final_out_control[source_id]['final_control']
                    previous_status = controller.final_out_control[source_id]['previous_final']
                    # Conduct the changed data of output and add to the message
                    if current_status != previous_status and instant_control == CONTROL_NEUTRAL and cloud_control == CONTROL_OFF:
                        dev_item = copy.deepcopy(template_device)
                        dev_item['source_id'] = source_id
                        dev_item['status_id'] = current_status
                        room_message['data'].append(dev_item)
                # Store the message in case sending would fail
                if len(room_message['data']) != 0:
                    if room_id not in controller.publish_messages.keys():
                        # Add new message of room
                        controller.publish_messages[room_id] = room_message
                    else:
                        # Update message of room
                        for new_output in room_message['data']:
                            new_src = new_output['source_id']
                            if new_output not in controller.publish_messages[room_id]['data']:
                                # Add new data of device
                                controller.publish_messages[room_id]['data'].append(new_output)
                            else:
                                # Check and update data of device
                                for pos in range(len(controller.publish_messages[room_id]['data'])):
                                    old_output = controller.publish_messages[room_id]['data'][pos]
                                    old_src = old_output['source_id']
                                    if new_src == old_src:
                                        controller.publish_messages[room_id]['data'][pos]['status_id'] = new_output['status_id']
                                        break
                # Prepare to publish by converting message, getting the topic to publish response to cloud
                if room_id in controller.publish_messages.keys() and controller.publish_messages[room_id] != {}:
                    published_message = json.dumps(controller.publish_messages[room_id])
                    topic = AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_CTL_RESULT_PUBLISH_TOPIC_STAGE
                    # Create a asynchronous process
                    input_arguments = {
                        "title": "Control_Sync",
                        "topic": topic,
                        "json": published_message,
                        "attempts_no": 0,
                        "attempts_limit": 0
                    }
                    # Start process operating publishing data to cloud
                    logger.info("[Control_output] Synchronizing current control status on room: " + str(room_id))
                    logger.info("[Control_output] Publishing control status message " + str(room_message) + " onto topic " + str(topic))
                    is_sent = AWSClient.publish_asynchronous(None, input_arguments)
                    # If the message is not sent successfully, store it to resend next time, otherwise remove it
                    if is_sent:
                        controller.publish_messages.pop(room_id)
    #[END OF FUNCTION][sync_ctl]############################################################################################

    # Handling subscribe to cloud for management data
    def get_mng_info(callback_function, arguments={}):
        # Subcribe to get message from AWS cloud
        logger.info("[Cloud] Subscribe on cloud to topic : " + str(AWS_TOPIC_PREFIX) + str(AWS_THING_NAME) + str(AWS_DEVICES_SUBSCRIBE_TOPIC_STAGE))
        try :
            AWSClient.subscribe_data(AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_DEVICES_SUBSCRIBE_TOPIC_STAGE, add_devices)
            logger.info("[Cloud] Completed management info subscription")
        except Exception as err:
            logger.error("[get devices] Internet connection problem, going to retry")
            time.sleep(5)
            # Retry subscription on a new thread
            if callable(callback_function):
                callback_function(get_mng_info)
    #[END OF FUNCTION][get_mng_info]########################################################################################

    # Split out a thread that send the message to cloud that request for list of managed devices
    def request_mng_info(callback_function, arguments):
        # While there is no devices in database, request cloud to send devices list in management
        ## Creating the init message to AWS cloud in order to update list of devices
        # Get current time
        dateTimeObj = datetime.now()
        timestampStr = dateTimeObj.strftime("%Y-%b-%d (%H:%M:%S.%f)")
        current_time = int(dateTimeObj.strftime('%s'))
        # Init message of Gateway
        gateway_message = {
            "state": {
                "reported": {
                "gateway": {
                    "mac_address": MAC_ADDR
                },
                "timestamp": timestampStr,
                "type": 1,
                "data": []
                }
            }
        }
        gateway_message = json.dumps(gateway_message)
        # Count attempt of publishing request
        arguments["try_no"] += 1
        # Extend log on retry
        extend_log = ""
        if arguments["try_no"] > 0:
            extend_log = "retry "
        # Try to publish if got no updated management info
        global get_devices_to_connect
        if get_devices_to_connect == False:
            if (current_time > REBOOT_LIMIT) and (arguments["try_no"] >= NUMBER_OF_RETRY_PUBLISHING):
                remove_file(REBOOT_TRACKFILE)
                write_to_file(REBOOT_TRACKFILE, str(current_time))
                # Restart Gateway application
                logger.error("[get devices] Cannot get devices to connect, going to restart Gateway application")
                os.system("reboot")
            else:
                min_sleep_time = 4
                AWSClient.publish_synchronous(AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_REQ_DEV_PUBLISH_TOPIC_STAGE, gateway_message, min_sleep_time)
                logger.info("[get devices] Requesting devices list, " + extend_log + "publishing init message " + str(gateway_message))
                # Escape loop, not retry to request device
                if get_devices_to_connect == False and callable(callback_function):
                    time.sleep(5)
                    callback_function(request_mng_info, arguments)
        time.sleep(0.001)
    #[END OF FUNCTION][request_mng_info]####################################################################################

    # Subcribe to get tracking data from AWS cloud
    def subscribe_tracking():
        logger.info("[data_tracking] Subscribing for data tracking")
        for i in range(0, NUMBER_OF_RETRY_SUBCRIBING):
            try :
                AWSClient.subscribe_data(AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_TRACKING_SUBSCRIBE_TOPIC_STAGE, get_tracking)
                logger.info("[data_tracking] Topic subscribed: " + str(AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_TRACKING_SUBSCRIBE_TOPIC_STAGE))
                time.sleep(5)
                break
            except Exception as err:
                logger.error("[data_tracking] Unable to subcribe on topic " + str(AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_TRACKING_SUBSCRIBE_TOPIC_STAGE) + ", error: " + str(err))
        time.sleep(0.001)
    #[END OF FUNCTION][request_tracking_data]###############################################################################

    # Subcribe to get control devices request from AWS cloud
    def subscribe_control():
        logger.info("[Control_output] Subscribing for control device request from Cloud")
        for i in range(0, NUMBER_OF_RETRY_SUBCRIBING):
            # logger.info("[Control_output] Subscribing for controlling devices")
            try :
                AWSClient.subscribe_data(AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_CONTROL_SUBSCRIBE_TOPIC_STAGE, handle_control_request)
                time.sleep(5)
                logger.info("[Control_output] Topic subscribed: " + str(AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_CONTROL_SUBSCRIBE_TOPIC_STAGE))
                break
            except Exception as err:
                logger.error("[Control_output] Unable to subcribe on topic " + str(AWS_TOPIC_PREFIX + AWS_THING_NAME + AWS_CONTROL_SUBSCRIBE_TOPIC_STAGE) + ", error: " + str(err))
        time.sleep(0.5)
    #[END OF FUNCTION][request_tracking_data]###############################################################################

    ### RUN INIT PROCESS ###
    ####################################################################
    logger.info("[get devices] Requesting devices list from cloud")
    # Update list of EnOcean devices into enoCommunicator model
    enoCommunicator.collect_devices()
    # Update list of EnOcean devices into modbusCommunicator model
    modbusCommunicator.collect_devices()
    # Start process operating subscription to management data topic
    get_mng_info(make_async_loop, {})
    time.sleep(3)
    # Start process operating publishing to cloud request getting management data
    make_async_loop(request_mng_info, {"try_no": 0})
    ####################################################################

    ####################################################################
    # Start the communicator models, this would start the main threads
    enoCommunicator.start()
    modbusCommunicator.start()
    time.sleep(0.5)
    AWSClient.start()
    controller.start()
    ####################################################################

    ####################################################################
    # Subscribe to some other services
    ## Subcribe to get tracking data from AWS cloud
    subscribe_tracking()
    ## Subcribe to get control devices request from AWS cloud
    subscribe_control()
    ## Make a thread that publish status of co2 control to cloud
    publish_co2_ctl_trg = threading.Event()
    publish_co2_control = threading.Thread(name='publish_co2_control', target=wait_publish_ctl, args=(publish_co2_ctl_trg, 10))
    publish_co2_control.start()
    ####################################################################

    # Ending of Application Initiation
    logger.info("[Init][End] End of IoT Gateway application Initiation")
