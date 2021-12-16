import time
import copy
from constant import *
from threading import Thread
from ..utils.function_library import *
from ..utils.lock_model import *
from ..utils.timer_process import event_timer
from openblock_gateway.communicators.localstorage.RoomModel import room
from openblock_gateway.communicators.localstorage.DevicesModel import devices
from openblock_gateway.communicators.localstorage.DataModel import data
from openblock_gateway.communicators.localstorage.database_interface import local_storage

class outputController(Thread):
    # outputController base-class.

    ####################################################################################################
    #[Function]: Initiate serial port
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   ttyPath {str} - Path to the ttySXXX file
    #   baudrate {int} - Baud rate of the serial port
    #[Return]: N/A
    ####################################################################################################
    def __init__(self, logger):
        super(outputController, self).__init__()
        self.logger = logger            # Logging object
        self.final_out_control = {}     # List of device used for operating the control process
        self.co2_data = {}              # Dictionary containing the CO2 value of the rooms
        self.publish_messages = {}      # Dictionary containing the messages should be sent to cloud to update status of output devices
        self.cloud_req_checked = CTL_CLD_NONE   # Status manage if receive cloud request in every minute
        # Define the lock on controlling devices to prevent chattering
        self.cloud_lock = lockModel("cloud_control", logger)
        self.offline_lock = lockModel("co2_control", logger)
        self.instant_lock = lockModel("instant_control", logger)
        # self.final_control = lockModel("final_control", logger)
        # Make thread to execute controlling devices by event trigger
        self.control_trigger = threading.Event()
        self.control_operator = threading.Thread(name='control_operator', target=self.wait_execute, args=(self.control_trigger, 10))
        # Make thread to operate according to CO2 by event trigger
        self.co2_process_trigger = threading.Event()
        self.co2_controller = threading.Thread(name='co2_controller', target=self.wait_co2_control, args=(self.co2_process_trigger, 10))
        # Make thread to update controlled devices list by event trigger
        self.management_trigger = threading.Event()
        self.management_updater = threading.Thread(name='management_updater', target=self.wait_manage, args=(self.management_trigger, 10))

    ####################################################################################################
    #[Function]: Update list of request from cloud
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   input_list {list} - list of devices info that needs to be changing status
    #[Return]:
    #   applied_list {list} - list of devices info that would be changing status
    ####################################################################################################
    def update_cloud_req(self, input_list):
        # self.logger.debug("[Control_output] update cloud request")
        is_auto_req = False
        applied_list = []   # List of outputs applied status after request
        if isinstance(input_list, list):
            for device_info in input_list:
                source_id = device_info[DV__SC_ID]
                request_value = device_info[DV__EX_PRT_1]
                control_id = device_info[DV__CTL_ID]
                # self.logger.debug("[Control_output] Checking " + str(source_id))
                # Only handle request on devices managed in self.final_out_control list
                if source_id in self.final_out_control.keys():
                    cloud_control = self.final_out_control[source_id]['cloud_control']
                    offline_control = self.final_out_control[source_id]['co2_control']
                    instant_control = self.final_out_control[source_id]['instant_control']
                    control_title = 'cloud_control'
                    # Handle the request
                    if request_value == CONTROL_ON_IMD or request_value == CONTROL_OFF_IMD:
                        control_title = 'instant_control'
                        # Execute instant control request
                        self.execute_instantly(source_id, control_title, request_value)
                        # Add source_id to applied outputs list in order to confirm to cloud
                        applied_list.append(source_id)
                    elif request_value == CONTROL_OFF_RMV:
                        # Execute immediate control when device is remove from control block on cloud
                        if control_id == CTL_ID_CO2:
                            # Apply to offline if get the control ID of control process via CO2
                            control_title = 'co2_control'
                        # Return status of the control back to OFF
                        self.final_out_control[source_id][control_title] = CONTROL_OFF
                        # Update Control ID to None
                        self.update_ctl_id(source_id, CTL_ID_NONE)
                        # Add source_id to applied outputs list in order to confirm to cloud
                        applied_list.append(source_id)
                        # Execute turning OFF the output
                        if offline_control == CONTROL_OFF and instant_control != CONTROL_ON:
                            request_value = CONTROL_OFF_IMD
                            # Turn off the output
                            self.execute_instantly(source_id, control_title, request_value)
                    elif request_value in VALID_CONTROL and self.cloud_req_checked != CTL_CLD_CONT:
                        # Handle the usual request of automatic control
                        is_auto_req = True
                        # Determine if it is mildew control
                        is_mld_ctl = False
                        if control_id == CTL_ID_MLD:
                            is_mld_ctl = True
                        # Store the previous status of cloud control
                        previous_out_vl = cloud_control
                        # Update to managed list in case of usual control
                        if (self.cloud_lock.validate(device_info, is_mld_ctl)):
                            self.final_out_control[source_id]['cloud_control'] = request_value
                            # Update Control ID
                            self.update_ctl_id(source_id, control_id)
                            # Execute request immediately if cloud request is just currently approved
                            if previous_out_vl != request_value and instant_control == CONTROL_NEUTRAL:
                                if request_value == CONTROL_ON:
                                    request_value = CONTROL_ON_IMD
                                elif request_value == CONTROL_OFF and offline_control == CONTROL_OFF:
                                    request_value = CONTROL_OFF_IMD
                                # Turn On/Off the output
                                self.execute_instantly(source_id, control_title, request_value)
                        if self.final_out_control[source_id]['cloud_control'] == device_info[DV__EX_PRT_1]:
                            if (device_info[DV__EX_PRT_1] == CONTROL_ON and instant_control != CONTROL_OFF) or (device_info[DV__EX_PRT_1] == CONTROL_OFF and instant_control != CONTROL_ON and offline_control == CONTROL_OFF):
                                # Add source_id to applied outputs list in order to confirm to cloud
                                applied_list.append(source_id)
                # Delay between each output
                time.sleep(0.001)
            # Reset flag managing the status receiving request from cloud every minute
            if is_auto_req:
                self.cloud_req_checked = CTL_CLD_CONT
            # self.logger.debug("[Control_output] self.final_out_control after cleaning through cloud request: " + str(self.final_out_control))
            return applied_list

    ####################################################################################################
    #[Function]: Update list of controlled output devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   source_id {str} - source id of device
    #   control_id {int} - control id of device
    #[Return]: N/A
    ####################################################################################################
    def update_ctl_id(self, source_id, control_id):
        # Update Control ID
        if self.final_out_control[source_id]['dev_info'][DV__CTL_ID] != control_id:
            dev_info = self.final_out_control[source_id]['dev_info']
            dev_info_list = list(self.final_out_control[source_id]['dev_info'])
            dev_info_list[DV__CTL_ID] = control_id
            self.final_out_control[source_id]['dev_info'] = tuple(dev_info_list)
            # Enocean device
            if dev_info[DV__MB_SV_ID] == 'NULL':
                update_device = devices(sourceid=dev_info[DV__SC_ID], devid=dev_info[DV__EN_DV_ID], channelid=dev_info[DV__CHN_ID], logger=self.logger)
            # Modbus device
            else:
                update_device = devices(sourceid=dev_info[DV__SC_ID], slaveid=dev_info[DV__MB_SV_ID], channelid=dev_info[DV__CHN_ID], logger=self.logger)
            # Update into database
            if update_device.ctl_id != control_id:
                update_device.ctl_id = control_id
                update_device.save()

    ####################################################################################################
    #[Function]: Calculate the final status should be apply on the devices base on cloud control, offline control and instant control
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   source_id {str} - source id of device
    #[Return]: N/A
    ####################################################################################################
    def calculate_operation(self, source_id):
        final_control = CONTROL_OFF
        # Combine all control commands
        if source_id in self.final_out_control.keys():
            cloud_control = self.final_out_control[source_id]['cloud_control']
            offline_control = self.final_out_control[source_id]['co2_control']
            instant_control = self.final_out_control[source_id]['instant_control']
            final_control = self.final_out_control[source_id]['final_control']
            # First priority is instant control, no need to prevent chattering; also neutralize stored instant control
            if instant_control != CONTROL_NEUTRAL:
                device_info = self.final_out_control[source_id]['dev_info'] + (CONTROL_NEUTRAL, ) 
                if self.instant_lock.validate(device_info):
                    self.final_out_control[source_id]['instant_control'] = CONTROL_NEUTRAL
                # Update for final command
                final_control = instant_control
            # Control according to cloud and co2, need to prevent chattering
            else:
                # Decide the value for final control value depending on cloud control and offline control
                if (cloud_control == CONTROL_ON) or (offline_control == CONTROL_ON):
                    temp_result = CONTROL_ON
                else:
                    temp_result = CONTROL_OFF
                # Apply control if passing allowed hold period
                final_control = temp_result
        return final_control

    ####################################################################################################
    #[Function]: Manage control operation periodically
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   event {} - object of class outputController
    #   timeout {int} - timeout in case of exception
    #[Return]: N/A
    ####################################################################################################
    def wait_manage(self, event, timeout):
        manage_timer = event_timer(event, CONTROL_STEP_DURATION, self.logger)
        periods_in_minute = KEEPING_OUTPUT_TIME / CONTROL_STEP_DURATION
        periods_no = 0
        reset_param = False
        while 1:
            # If pass a minute, then set periods_no param to notify to reset waiting for cloud request at every minute
            periods_no += 1
            if periods_no >= periods_in_minute:
                periods_no = 0
                reset_param = True
            else:
                reset_param = False
            time.sleep(0.0001)
            # Wait for the event
            event_is_set = event.wait(timeout)
            # Execute the process when event is set
            if event_is_set:
                # Operate controlling
                self.update_management(reset_param)
            else:
                # Handle timeout if any process is needed
                pass
            event.clear()

    ####################################################################################################
    #[Function]: Update lists used for controlling
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   reset_param {bool} - param notifies to reset waiting for cloud request at every minute
    #[Return]: N/A
    ####################################################################################################
    def update_management(self, reset_param):
        # Query database to get controlled EnOcean output devices
        controlled_devices = devices(direction=1, logger=self.logger)
        temp_out_list = controlled_devices.get_data()
        # Update list of controlled output devices
        self.update_output_dev_list(temp_out_list, reset_param)
        # Update output chattering managing list
        self.cloud_lock.update_list(self.final_out_control)
        self.offline_lock.update_list(self.final_out_control)
        self.instant_lock.update_list(self.final_out_control)

    ####################################################################################################
    #[Function]: Update list of controlled output devices
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   latest_out_list {list} - object of class outputController
    #   reset_param {bool} - param notifies to reset waiting for cloud request at every minute
    #[Return]: N/A
    ####################################################################################################
    def update_output_dev_list(self, latest_out_list, reset_param):
        # Update output controlling list
        if len(latest_out_list) != 0:
            updated_list = {}
            try:
                # Loop to delete device in status controlling list if device is removed in managed devices list
                for key in self.final_out_control.keys():
                    # key is source_id of the device
                    for managed_device in latest_out_list:
                        dev_source_id = managed_device[DV__SC_ID]
                        if key == dev_source_id:
                            updated_list[key] = self.final_out_control[key]
                            if managed_device != updated_list[key]['dev_info']:
                                updated_list[key]['dev_info'] = managed_device
                            # Update the control value
                            updated_list[key]['previous_final'] = updated_list[key]['final_control']
                            updated_list[key]['final_control'] = self.calculate_operation(key)
                            break
                    time.sleep(0.001)
                # Loop to add device in managed devices list to output controlling list
                for managed_device in latest_out_list:
                    # Check if this device does not exist in output controlling list then add it
                    dev_source_id = managed_device[DV__SC_ID]
                    if dev_source_id not in updated_list:
                        updated_list[dev_source_id] = {
                            'dev_info': managed_device,
                            'cloud_control': CONTROL_OFF,
                            'co2_control': CONTROL_OFF,
                            'instant_control': CONTROL_NEUTRAL,
                            'final_control': CONTROL_OFF,
                            'previous_final': CONTROL_OFF
                        }
                    time.sleep(0.001)
                # Update latest status to self.final_out_control
                self.final_out_control = updated_list
                # self.logger.info("[Control_output] Current output devices list is " + str(self.final_out_control))
            except Exception as err:
                self.logger.error("[Control_output] Not able to collect current output devices, error: " + str(err))
        # Reset checking process for cloud request at every minute
        if reset_param:
            self.cloud_req_checked = CTL_CLD_WAIT
            self.logger.info("[Control_output] Current managed outputs information: " + str(self.final_out_control))

    ####################################################################################################
    #[Function]: Manage co2 control operation periodically
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   event {} - object of class outputController
    #   timeout {int} - timeout in case of exception
    #[Return]: N/A
    ####################################################################################################
    def wait_co2_control(self, event, timeout):
        co2_timer = event_timer(event, CONTROL_STEP_DURATION, self.logger)
        while 1:
            time.sleep(0.0001)
            event_is_set = event.wait(timeout)
            if event_is_set:
                # Operate controlling
                self.co2_operate()
            else:
                # Handle timeout if any process is needed
                pass
            event.clear()

    ####################################################################################################
    #[Function]: Calculate the CO2 of every room and apply control to each related device
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #[Return]: N/A
    ####################################################################################################
    def co2_operate(self):
        self.db = local_storage(logger=self.logger)
        list_of_rooms = self.db.query_data("rooms")
        old_room_list = copy.deepcopy(self.co2_data)
        # Remove old room due to data from database
        for old_room in old_room_list.keys():
            if old_room not in list_of_rooms:
                self.co2_data.pop(old_room)
        # Collect data by rooms
        for room in list_of_rooms:
            room_id = room[RM__ROOM_ID]
            data_to_query = {'room' : room_id}
            co2_results = []
            try:
                # Getting the CO2 sensors value of the room
                list_of_devices = self.db.query_data("devices", data_to_query)
                if len(list_of_devices) != 0:
                    for device in list_of_devices:
                        if (device[DV__TYPE] in CO2_CALCULATE_INFO.keys()) and device[DV__CO2_POS] == 2 and (device[DV__STATUS] == 1):
                            if device[DV__TYPE] == 'gmw83drp-sensor' and device[DV__VAL_TYPE] != 1:
                                continue
                            device_id = ""
                            slave_id = ""
                            if device[DT__EN_DV_ID] != "NULL":
                                device_id = device[DT__EN_DV_ID]
                            elif device[DT__MB_SV_ID] != "NULL":
                                slave_id = device[DT__MB_SV_ID]
                            data_of_device = data(sourceid=device[DV__SC_ID], devid=device_id, slaveid=slave_id, channelid=device[DT__CHN_ID], logger=self.logger)
                            if type(data_of_device.co2_value) == int and data_of_device.co2_value > CO2_IGNORE_VL:
                                co2_results.append(int(data_of_device.co2_value))
                co2_average = 0
                # Calculating the avarage of the CO2 value in the room
                if len(co2_results) > 0:
                    sum = 0
                    for single_value in co2_results:
                        sum += single_value
                    co2_average = int(sum / len(co2_results))
                self.co2_data[room_id] = co2_average
            except Exception as err:
                self.logger.error("[Control_output] Failed to give command; " + str(err))
        # self.logger.info("[Control_output] list CO2 of rooms is " + str(self.co2_data))
        # Apply CO2 control to output devices
        self.offline_apply_by_room()

    ####################################################################################################
    #[Function]: Update list of controlled output devices by rooms
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #[Return]: N/A
    ####################################################################################################
    def offline_apply_by_room(self):
        # self.co2_changes = {}
        for source_id in self.final_out_control.keys():
            # if source_id in self.final_out_control.keys():
            device = self.final_out_control[source_id]['dev_info']
            co2_lo_limit = 0
            co2_hi_limit = 0
            if type(device[DV__CTLCO2_MIN]) == int:
                co2_lo_limit = device[DV__CTLCO2_MIN]
            if type(device[DV__CTLCO2_MAX]) == int:
                co2_hi_limit = device[DV__CTLCO2_MAX]
            room_id = device[DV__ROOM]
            if room_id in self.co2_data.keys():
                co2_control = self.final_out_control[source_id]['co2_control']
                cloud_control = self.final_out_control[source_id]['cloud_control']
                instant_control = self.final_out_control[source_id]['instant_control']
                final_control = self.final_out_control[source_id]['final_control']
                # previous_value = co2_control
                if co2_lo_limit == co2_hi_limit or co2_hi_limit == 0:
                    # If control is invalid on the device, turn OFF the CO2 control on this device
                    if co2_control != CONTROL_OFF:
                        co2_control = CONTROL_OFF_IMD
                        self.final_out_control[source_id]['co2_control'] = co2_control
                        # Turn off the output
                        self.execute_instantly(source_id, 'co2_control', co2_control)
                elif room_id in self.co2_data.keys():
                    room_co2 = self.co2_data[room_id]
                    # Determine if the output device should be change status
                    if (room_co2 >= co2_hi_limit):
                        # self.logger.info("[Control_output] CO2 of room " + str(room_id) + " is at high level, purifier shall turn on " + str(source_id))
                        co2_control = CONTROL_ON
                    elif (room_co2 <= co2_lo_limit):
                        # self.logger.info("[Control_output] CO2 of room " + str(room_id) + " is at low level, stop operating " + str(source_id))
                        co2_control = CONTROL_OFF
                    else:
                        pass
                    dev_info = device + (co2_control, )
                    # self.logger.info("[Control_output] CO2 control temp command on " + str(source_id) + " is " + str(co2_control))
                    # Validate and apply the value of CO2 control based on delay
                    if self.offline_lock.validate(dev_info):
                        self.final_out_control[source_id]['co2_control'] = co2_control

    ####################################################################################################
    #[Function]: Execute control operation periodically
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   event {} - object of class outputController
    #   timeout {int} - timeout in case of exception
    #[Return]: N/A
    ####################################################################################################
    def wait_execute(self, event, timeout):
        execution_timer = event_timer(event, CONTROL_STEP_DURATION, self.logger)
        while 1:
            time.sleep(0.0001)
            event_is_set = event.wait(timeout)
            if event_is_set:
                # Operate controlling
                self.execute()
            else:
                # Handle timeout if any process is needed
                pass
            event.clear()

    ####################################################################################################
    #[Function]: Execute control operation
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #[Return]: N/A
    ####################################################################################################
    def execute(self):
        for source_id in self.final_out_control.keys():
            device = self.final_out_control[source_id]
            device_info = device['dev_info']
            requested_value = device['final_control']
            try:
                # Save requested status of output channel into database
                # Enocean device
                dmd_data = None
                if device_info[DV__MB_SV_ID] == 'NULL':
                    dmd_data = data(sourceid=device_info[DV__SC_ID], devid=device_info[DV__EN_DV_ID], channelid=device_info[DV__CHN_ID], logger=self.logger)
                # Modbus device
                else:
                    dmd_data = data(sourceid=device_info[DV__SC_ID], slaveid=device_info[DV__MB_SV_ID], channelid=device_info[DV__CHN_ID], logger=self.logger)
                # Apply requested value if changed
                if (dmd_data.data_dev == "") or (dmd_data.data_dev.isnumeric() and dmd_data.data_dev != int(requested_value)):
                    # self.logger.info("[Control_output] Going to apply command on " + str(source_id))
                    dmd_data.data_dev = requested_value
                    dmd_data.save()
            except Exception as err:
                self.logger.error("[Control_output] Failed to verify and apply control request for output, error:" + str(err))

    ####################################################################################################
    #[Function]: Execute instant control operation
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #   source_id {str} - source id of the output device
    #   control_process {str} - control title determine if it relates to cloud control or instant control
    #   requested_value {int} - the value that output device needs to be set to
    #[Return]: N/A
    ####################################################################################################
    def execute_instantly(self, source_id, control_process, requested_value):
        if source_id in self.final_out_control.keys():
            device = self.final_out_control[source_id]
            device_info = device['dev_info']
            # Convert to usual control value to store on the managing list
            temp_request = CONTROL_NEUTRAL
            if requested_value == CONTROL_ON_IMD:
                temp_request = CONTROL_ON
            elif requested_value == CONTROL_OFF_IMD:
                temp_request = CONTROL_OFF
            # Update temporary value base on control process
            self.final_out_control[source_id][control_process] = temp_request
            if control_process == 'instant_control':
                self.instant_lock.set_current_state(source_id, temp_request)
            elif control_process == 'cloud_control':
                self.cloud_lock.set_current_state(source_id, temp_request)
            elif control_process == 'co2_control':
                self.offline_lock.set_current_state(source_id, temp_request)
            time.sleep(0.001)
            # Store it on the final control value in the managing list
            self.final_out_control[source_id]['final_control'] = self.calculate_operation(source_id)
            self.final_out_control[source_id]['previous_final'] = self.final_out_control[source_id]['final_control']
            time.sleep(0.001)
            requested_value = int(self.final_out_control[source_id]['final_control']) + 2
            # Save requested status of output channel into database
            try:
                # Enocean device
                if device_info[DV__MB_SV_ID] == 'NULL':
                    dmd_data = data(sourceid=device_info[DV__SC_ID], devid=device_info[DV__EN_DV_ID], channelid=device_info[DV__CHN_ID], logger=self.logger)
                # Modbus device
                else:
                    dmd_data = data(sourceid=device_info[DV__SC_ID], slaveid=device_info[DV__MB_SV_ID], channelid=device_info[DV__CHN_ID], logger=self.logger)
                # Apply requested value if changed
                if dmd_data.data_dev != requested_value:
                    dmd_data.data_dev = requested_value
                    dmd_data.save()
                # self.logger.info("[Control_output] Control value of " + str(device_info[DV__SC_ID]) + " is " + str(requested_value))
            except Exception as err:
                self.logger.error("[Control_output] Failed to verify and apply control request for output, error:" + str(err))

    ####################################################################################################
    #[Function]: Main process
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {outputController} - object of class outputController
    #[Return]: N/A
    ####################################################################################################
    def run(self):
        self.logger.info("[Control_output] Start")
        # Update managed output devices list
        self.management_updater.start()
        time.sleep(10)
        # Start process Controlling according to CO2
        self.co2_controller.start()
        time.sleep(10)
        # Start the thread in which managing control execution periodically
        self.control_operator.start()
