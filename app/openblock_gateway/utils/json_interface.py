from random import seed
from random import randint
from constant import *

# seed random number generator
seed(1)

def valid_assign(default_value, input_value, backward_start):
    # If type of input is not as expected, or input is empty string, or input length is too short to extract needed value then return a default value
    if (type(input_value) != type(default_value)) \
       or (type(input_value) == str and (input_value == "" or len(input_value) < backward_start)):
        return default_value
    data_to_return = None
    # Handle string type input value
    if (type(input_value) == str):
        data_to_return = ""
        default_len = len(default_value)
        input_len = len(input_value)
        valid_len = input_len - backward_start
        # Normal case
        if valid_len >= default_len:
            start_pos = valid_len - default_len
            data_to_return = input_value[start_pos:valid_len]
        # If the extracted value lenght is shorter than expected as default value then add 0 to the front
        else:
            len_dif = default_len - valid_len
            start_pos = 0
            data_to_return = input_value[start_pos:valid_len]
            for i in range(len_dif):
                data_to_return = "0" + data_to_return
    return data_to_return

def to_json(device_info):
    # Declare variables
    json_return = {}
    try:
        device_type = device_info['type']
        device_data = device_info['data']
        data_len = len(device_data)
        json_return['device_id'] = device_info['source_id']
        json_return['type'] = device_type
        # Handle EnOcean device
        if 'deviceId' in device_info.keys():
            device_id = device_info['deviceId']
            # Handle CO2-928 sensor
            if device_type == 'co2-928-sensor':
                json_return['d_position'] = device_info['d_position']   # Position of the sensor related to CO2 concentration (Indoor/Outdoor)
                # Handle all Temperature, CO2 concentration, Humidity data in one package
                temperature = valid_assign("00", device_data, 0)
                co2_concen = valid_assign("00", device_data, 2)
                humidity = valid_assign("00", device_data, 4)
                json_return['values'] = {
                    't': temperature,
                    'co2': co2_concen,
                    'r': humidity
                }
            # Handle ETB-SIC-P sensor
            elif device_type == 'etb-sic-p-sensor':
                presure = valid_assign("00", device_data, 0)
                json_return['values'] = {'pr': presure}
        # Handle Modbus device
        elif 'slaveId' in device_info.keys():
            slaveId = device_info['slaveId']
            channelAddressId = device_info['channelAddressId']
            # Handle GMD20 sensor
            if device_type == 'gmd20-sensor':
                json_return['d_position'] = device_info['d_position']   # Position of the sensor related to CO2 concentration (Indoor/Outdoor)
                co2_concen = valid_assign("0000", device_data, 0)
                json_return['values'] = {'co2': co2_concen}
            # Handle GMW83 sensor
            elif device_type == 'gmw83drp-sensor' :
                json_return['d_position'] = device_info['d_position']   # Position of the sensor related to CO2 concentration (Indoor/Outdoor)
                # Handle CO2 data
                if device_info['v_type'] == 1:
                    co2_concen = valid_assign("0000", device_data, 0)
                    json_return['values'] = {'co2': co2_concen}
                # Handle Temperature data
                elif device_info['v_type'] == 2:
                    temperature = valid_assign("0000", device_data, 0)
                    json_return['values'] = {'t': temperature}
                # Handle Humidity data
                elif device_info['v_type'] == 3:
                    humidity = valid_assign("0000", device_data, 0)
                    json_return['values'] = {'r': humidity}
    except Exception as err:
        # Return empty if any error
        return {}
    # Return empty if values field is invalid
    if 'values' not in json_return.keys():
        return {}
    # If no issue occurs, return the formatted json data
    return json_return

def set_device_directions(device_type):
    # device_type = device_info['type']
    if device_type in SENSOR_DEVICES_LIST:
        return 2
    elif device_type in CONTROL_MODULES_LIST:
        return 2
    elif device_type in TRACKING_DEVICES_LIST:
        return 2
    return 1

def form_json_for_gmw83drp_device(list_of_devices_in_room):
    # Define sample for list of checking GMW83DRP devices
    checklist = {}
    checking_object = {
        "flag_gmw83_co2": False,
        "flag_gmw83_t": False,
        "flag_gmw83_r": False
    }
    # Result list
    list_of_gmw83drp = []
    json_list_of_devices = []
    for checking_device in list_of_devices_in_room:
        try:
            if checking_device['type'] == 'gmw83drp-sensor':
                checking_source_id = checking_device['device_id']
                # Create item in result list if not exist
                if checking_source_id not in checklist.keys():
                    # Add to checklist
                    checklist[checking_source_id] = checking_object
                    # Add to list of GMW83DRP
                    temp_dict = {
                        'values': {},
                        'type': 'gmw83drp-sensor',
                        'd_position': checking_device['d_position'],
                        'device_id': checking_source_id
                    }
                    list_of_gmw83drp.append(temp_dict)
                # Assign value of each channel and check valid
                for dict_of_gmw83drp in list_of_gmw83drp:
                    if dict_of_gmw83drp['device_id'] == checking_source_id:
                        checking_value_field = checking_device['values']
                        # Update value in case of CO2 channel
                        if 'co2' in checking_value_field.keys():
                            checklist[checking_source_id]["flag_gmw83_co2"] = True
                            dict_of_gmw83drp['values']['co2'] = checking_value_field['co2']
                        # Update value in case of Temperature channel
                        elif 't' in checking_value_field.keys():
                            checklist[checking_source_id]["flag_gmw83_t"] = True
                            dict_of_gmw83drp['values']['t'] = checking_value_field['t']
                        # Update value in case of Humidity channel
                        elif 'r' in checking_value_field.keys():
                            checklist[checking_source_id]["flag_gmw83_r"] = True
                            dict_of_gmw83drp['values']['r'] = checking_value_field['r']
                        # Escape loop after updating the right element
                        break
            else :
                json_list_of_devices.append(checking_device)
        except:
            continue
    # Push data of GMW83DRP sensor into output json package
    for gmw83_device in list_of_gmw83drp:
        # Get source ID of the GMW83DRP sensor
        source_id = gmw83_device["device_id"]
        # Get confirmation on data of each channel is collected
        flag_gmw83_co2 = checklist[source_id]["flag_gmw83_co2"]
        flag_gmw83_t = checklist[source_id]["flag_gmw83_t"]
        flag_gmw83_r = checklist[source_id]["flag_gmw83_r"]
        # Check if all channels of GMW83DRP sensor contain valid data then push it into json
        if flag_gmw83_co2 == True and flag_gmw83_t == True and flag_gmw83_r == True:
            json_list_of_devices.append(gmw83_device)

    return json_list_of_devices