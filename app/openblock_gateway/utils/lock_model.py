import time
from constant import *
from configuration import *
from threading import Thread
from openblock_gateway.communicators.localstorage.RoomModel import room
from openblock_gateway.communicators.localstorage.DevicesModel import devices
from openblock_gateway.communicators.localstorage.DataModel import data
from openblock_gateway.communicators.localstorage.database_interface import local_storage
from ..utils.function_library import *

class lockModel():
    # lockModel base-class

    ####################################################################################################
    #[Function]: Initiate lock item
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   control_title {str} - title determine this lock related to which control process
    #   logger {logging} - logging operator object
    #[Return]: N/A
    ####################################################################################################
    def __init__(self, control_title, logger):
        self.logger = logger
        self.verified_outputs = {}
        self.title = control_title

    ####################################################################################################
    #[Function]: Update the existence of the output devices that are currently managed
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   out_channels_list {list} - list of devices connected to output channels
    #[Return]: N/A
    ####################################################################################################
    def update_list(self, out_channels_list):
        # Update output management list
        ## Remove old items
        removed_list = []
        for existing_id in self.verified_outputs.keys():
            is_removed = True
            for new_src_id in out_channels_list.keys():
                control_info = out_channels_list[new_src_id]
                if existing_id == new_src_id:
                    # If no matched output remaining in the new list then remove this item
                    is_removed = False
                    if control_info[self.title] != self.verified_outputs[existing_id]['current_state']:
                        self.verified_outputs[existing_id]['current_state'] = control_info[self.title]
                        self.verified_outputs[existing_id]['toggle_request_no'] = 0
                    break
                time.sleep(0.001)
            if is_removed:
                removed_list.append(existing_id)
        for removed_source_id in removed_list:
            self.remove_output(removed_source_id)
        ## Add new items
        for source_id in out_channels_list.keys():
            channel_info = out_channels_list[source_id]['dev_info']
            device_id = channel_info[DV__EN_DV_ID]
            channel_id = channel_info[DV__CHN_ID]
            # Add new item into verified_outputs list
            if source_id not in self.verified_outputs.keys():
                # Get the current set value
                data_from_database = data(sourceid=source_id, devid=device_id, channelid=channel_id, logger=self.logger)
                db_value = CONTROL_OFF
                if hasattr(data_from_database, "data_dev") and data_from_database.data_dev != '':
                    db_value = int(data_from_database.data_dev)
                # Get the current requested output value of the channel
                self.insert_output(source_id, db_value)

    ####################################################################################################
    #[Function]: Insert lock state of output channel to prevent chattering phenomenon
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   source_id {str} - Source Id of the devices connected to DO channel
    #   set_value {int} - Output value is set to DO channel
    #[Return]: N/A
    ####################################################################################################
    def insert_output(self, source_id="", set_value=CONTROL_OFF):
        if (source_id == ""):
            return
        init_lock_info = {
            "current_state": int(set_value),
            "toggle_request_no": 0
        }
        self.verified_outputs[source_id] = init_lock_info

    ####################################################################################################
    #[Function]: Remove lock state of output channel to prevent chattering phenomenon
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   source_id {str} - Source Id of the devices connected to DO channel
    #[Return]: N/A
    ####################################################################################################
    def remove_output(self, source_id):
        self.verified_outputs.pop(source_id, None)

    ####################################################################################################
    #[Function]: Validate lock state of output channel to prevent chattering phenomenon
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   channel_info {tuple} - info of the devices connected to DO channel
    #   is_mld_ctl {bool} - define is it controlling by mildew or not to get the required number of requests correctly
    #[Return]: N/A
    ####################################################################################################
    def validate(self, channel_info=(), is_mld_ctl=False):
        is_request_allowed = False
        source_id = channel_info[DV__SC_ID]
        if source_id not in self.verified_outputs.keys():
            return False
        current_value = self.verified_outputs[source_id]["current_state"]
        request_value = int(channel_info[DV__EX_PRT_1])
        if request_value == CONTROL_ON_IMD or request_value == CONTROL_OFF_IMD:
            return False
        # Get required request number to control device
        periods_in_minute = 1
        if self.title != 'cloud_control':
            periods_in_minute = KEEPING_OUTPUT_TIME / CONTROL_STEP_DURATION
        required_req_no = REQUIRED_CTL_REQ_NO * periods_in_minute
        # Get mildew delay if it is cloud control by mildew risk
        if is_mld_ctl and (request_value == CONTROL_ON):
            required_req_no = channel_info[DV__MLD_TIME_ON] * periods_in_minute
        elif is_mld_ctl and (request_value == CONTROL_OFF):
            required_req_no = channel_info[DV__MLD_TIME_OFF] * periods_in_minute
        # Otherwise use the common delay value
        elif (request_value == CONTROL_ON) or (current_value == CONTROL_OFF and request_value == CONTROL_NEUTRAL):
            required_req_no = channel_info[DV__TIME_ON] * periods_in_minute
        elif (request_value == CONTROL_OFF) or (current_value == CONTROL_ON and request_value == CONTROL_NEUTRAL):
            required_req_no = channel_info[DV__TIME_OFF] * periods_in_minute
        # Handle lock on DO channel
        if request_value == self.verified_outputs[source_id]["current_state"]:
            # If it is not toggle request, reset counting of the toggle requests
            self.verified_outputs[source_id]["toggle_request_no"] = 0
            is_request_allowed = False
        else:
            # If it is toggle request, sum up the toggle requests from cloud
            self.verified_outputs[source_id]["toggle_request_no"] += 1
            # Validate if number of toggle request reaches required amount then allow to apply this request
            if self.verified_outputs[source_id]["toggle_request_no"] > required_req_no:
                # Allow to set output if the same requested state reached required amount times
                is_request_allowed = True
                # Overwrite the old lock with new one which has the toggled state on DO channel
                self.verified_outputs[source_id]["current_state"] = request_value
                self.verified_outputs[source_id]["toggle_request_no"] = 0
                # self.logger.info("[lock] validated ok and going to apply output value " + str(request_value) + " to " + str(source_id))
            else:
                is_request_allowed = False
        # Return result whether allowing toggle DO channel or not
        return is_request_allowed

    ####################################################################################################
    #[Function]: Get current number of request received on a device
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   source_id {str} - source ID of the device
    #[Return]:
    #   toggle_request_no {int} - received request number of the device
    ####################################################################################################
    def get_req_no(self, source_id):
        # self.logger.info("[lock] Set current request number on" + str(source_id))
        if source_id in self.verified_outputs.keys():
            return self.verified_outputs[source_id]["toggle_request_no"]
        else:
            return None

    ####################################################################################################
    #[Function]: Get current status of a device
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   source_id {str} - source ID of the device
    #[Return]:
    #   current_state {int} - received request number of the device
    ####################################################################################################
    def get_current_state(self, source_id):
        # self.logger.info("[lock] Get current output value on" + str(source_id))
        if source_id in self.verified_outputs.keys():
            return self.verified_outputs[source_id]["current_state"]
        else:
            return None

    ####################################################################################################
    #[Function]: Update current state
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   source_id {str} - source ID of the device
    #   state {int} - current state of the control
    #[Return]: N/A
    ####################################################################################################
    def set_current_state(self, source_id, state):
        # Count up the toggle request number
        # self.logger.info("[lock] Set current output value on" + str(source_id))
        if state != self.verified_outputs[source_id]["current_state"]:
            self.verified_outputs[source_id]["toggle_request_no"] = 0
        self.verified_outputs[source_id]["current_state"] = state

    ####################################################################################################
    #[Function]: Count up the toggle request number
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   source_id {str} - source ID of the device
    #[Return]: N/A
    ####################################################################################################
    def lower_lock(self, source_id):
        # Count up the toggle request number
        # self.logger.info("[lock] releasing locking output value on" + str(source_id))
        self.verified_outputs[source_id]["toggle_request_no"] += 1

    ####################################################################################################
    #[Function]: Count up the toggle request number and also set the current state of the lock
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {lockModel} - object of class lockModel
    #   source_id {str} - Source ID of the device
    #   state {int} - current state of the control
    #[Return]: N/A
    ####################################################################################################
    def pass_lock(self, source_id, state):
        self.lower_lock(source_id)
        self.set_current_state(source_id, state)
