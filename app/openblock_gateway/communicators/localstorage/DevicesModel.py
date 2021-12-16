from typing import ChainMap
from .database_interface import local_storage
from constant import *

class devices:

    def __init__(self, sourceid="", devid="", slaveid="", channelid="", room="", protocol=0, status=2, \
                             devtype="", direction=0, position=0, valtype=0, co2_hex='', co2_dec=0, co2_sup=0, \
                             inverted=0, rlsourceid="", ctl_id=0, ctl_co2_min=0, ctl_co2_max=0, \
                             ctl_delay_on=0, ctl_delay_off=0, mld_delay_on=0, mld_delay_off=0, logger=""):
        self.source_id = sourceid
        # In case of Enocean devices data, store devid
        if devid != "" and slaveid == "":
            self.dev_id = devid
        # In case of Modbus devices data, store slaveid
        elif devid == "" and slaveid != "":
            self.slave_id = slaveid
        # In case channel id exists, store channel_id
        if channelid != "" :
            self.channel_id = channelid
        # Store other info
        self.protocol = protocol
        self.status = status
        self.type = devtype
        self.room = room
        self.direction = direction
        self.position = position
        self.value_type = valtype
        self.co2_hex = co2_hex
        self.co2_dec = co2_dec
        self.co2_sup = co2_sup
        self.inverted = inverted
        self.related_source_id = rlsourceid
        self.ctl_id = ctl_id
        self.ctl_co2_min = ctl_co2_min
        self.ctl_co2_max = ctl_co2_max
        self.ctl_delay_on = ctl_delay_on
        self.ctl_delay_off = ctl_delay_off
        self.mld_delay_on = mld_delay_on
        self.mld_delay_off = mld_delay_off
        self.table = "devices"
        self.columns = {
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
        self.db = local_storage(logger=logger)
        self.logger = logger
        # Create table based on table name and the columns titles
        # Init data in table
        device_info = ()
        if devtype == "":
            # In case of Enocean sensor devices data, identify by devid
            if hasattr(self, 'dev_id') and not hasattr(self, 'slave_id'):
                data = {'devId' : self.dev_id, 'slaveId' : 'NULL', 'channelId' : 'NULL'}
                if hasattr(self, 'channel_id') and self.channel_id != 'NULL':
                    data['channelId'] = self.channel_id
                device_info = self.db.get_first_row(self.table, data)
            # In case of Modbus devices data, identify by slave_id and channelid
            elif hasattr(self, 'slave_id') and not hasattr(self, 'dev_id'):
                data = {'devId' : 'NULL', 'slaveId' : self.slave_id, 'channelId' : 'NULL'}
                if hasattr(self, 'channel_id') and self.channel_id != 'NULL':
                    data['channelId'] = self.channel_id
                device_info = self.db.get_first_row(self.table, data)
            # In case there is only source ID, recover device id or slave id then channel id (if any)
            elif hasattr(self, 'source_id'):
                data = {'source' : self.source_id}
                device_info = self.db.get_first_row(self.table, data)
                if device_info != ():
                    if device_info[DV__EN_DV_ID] != 'NULL':
                        self.devId = device_info[DV__EN_DV_ID]
                    if device_info[DV__MB_SV_ID] != 'NULL':
                        self.slave_id = device_info[DV__MB_SV_ID]
                    if device_info[DV__CHN_ID] != 'NULL':
                        self.channel_id = device_info[DV__CHN_ID]
            # Cover missing info
            if device_info != ():
                self.protocol = device_info[DV__PROTOCOL]
                self.room = device_info[DV__ROOM]
                self.status = device_info[DV__STATUS]
                self.type = device_info[DV__TYPE]
                self.direction = device_info[DV__DIRECTION]
                self.position = device_info[DV__CO2_POS]
                self.value_type = device_info[DV__VAL_TYPE]
                self.co2_hex = device_info[DV__CO2_HEX]
                self.co2_dec = device_info[DV__CO2_DEC]
                self.co2_sup = device_info[DV__CO2_SUP]
                self.inverted = device_info [DV__INVERTED]
                self.related_source_id = device_info[DV__RELATED_SC_ID]
                self.ctl_id = device_info[DV__CTL_ID]
                self.ctl_co2_min = device_info[DV__CTLCO2_MIN]
                self.ctl_co2_max = device_info[DV__CTLCO2_MAX]
                self.ctl_delay_on = device_info[DV__TIME_ON]
                self.ctl_delay_off = device_info[DV__TIME_OFF]
                self.mld_delay_on = device_info[DV__MLD_TIME_ON]
                self.mld_delay_off = device_info[DV__MLD_TIME_OFF]

    def get_columns(self):
        return self.columns

    def get_table(self):
        return self.table

    def get_data(self):
        data = {}
        # Add source key to queried data if self.source_id exists
        if hasattr(self, 'source_id') and self.source_id != '':
            data = {'source' : self.source_id}
        # Add device id key to queried data if self.dev_id exists
        if hasattr(self, 'dev_id') and self.dev_id != '' and self.dev_id != 'NULL':
            data = {'devId' : self.dev_id, 'slaveId' : 'NULL'}
        # Add slave id key to queried data if self.slave_id and self.channel_id exist
        if hasattr(self, 'slave_id') and self.slave_id != '' and self.slave_id != 'NULL':
            data = {'devId' : 'NULL', 'slaveId' : self.slave_id}
        # Add channel id key to queried data if self.channel_id exists
        if hasattr(self, 'channel_id') and self.channel_id != '':
            data['channelId'] = self.channel_id
        # Add protocol key to queried data if self.protocol is 1 or 3
        if hasattr(self, 'protocol') and (int(self.protocol) >= 1 and int(self.protocol) <= 3):
            data['protocol'] = self.protocol
        # Add room key to queried data if self.room exists
        if hasattr(self, 'room') and self.room != '':
            data['room'] = self.room
        # Add direction key to queried data if self.direction exists and not equal 0
        if hasattr(self, 'direction') and self.direction != 0:
            data['direction'] = self.direction
        # Add device type key to queried data if self.type exists and not empty
        if hasattr(self, 'type') and self.type != '':
            data['type'] = self.type
        # Query data from data table with condition from data
        query_result = self.db.query_data(self.table, data)
        # self.logger.info("[data_model]query_result: " + str(query_result))
        return query_result

    # Compare an input value to the expected default value
    def valid_assign(self, input_value, default_value):
        data_to_return = input_value
        # Handle specifically for string
        if (type(input_value) == str and input_value == ""):
            data_to_return = default_value
        # Handle specifically for integer
        if (type(default_value) == int):
            try:
                # Force to assign as integer type, in case input data is string
                data_to_return = int(input_value)
            except Exception as int_ex:
                # If fail to force type then return the valid default value
                data_to_return = default_value
        # Validate type of setting value before return
        if (type(data_to_return) != type(default_value)):
            data_to_return = default_value
        return data_to_return

    def save(self):
        # Prepare data to query on based on deviceID/slaveID and channelID if exists
        data = {}
        if hasattr(self, 'dev_id') and self.dev_id != '':
            data = {'devId' : self.dev_id, 'slaveId' : 'NULL', 'channelId' : 'NULL'}
        elif hasattr(self, 'slave_id') and self.slave_id != '':
            data = {'devId' : 'NULL', 'slaveId' : self.slave_id, 'channelId' : 'NULL'}
        if hasattr(self, 'channel_id') and self.channel_id != '':
            data['channelId'] = self.valid_assign(self.channel_id, 'NULL')
        # Query to determine row in table then update to the queried row if exists
        try:
            # Query to find if device already existed
            query_result = self.db.query_data(self.table, data)
            # Update other info of device
            data['source'] = self.valid_assign(self.source_id, 'NULL')
            data['room'] = self.valid_assign(self.room, 'NULL')
            data['protocol'] = self.valid_assign(self.protocol, 0)
            data['status'] = self.valid_assign(self.status, 2)
            data['type'] = self.valid_assign(self.type, 'NULL')
            data['direction'] = self.valid_assign(self.direction, 2)
            data['position'] = self.valid_assign(self.position, 0)
            data['valueType'] = self.valid_assign(self.value_type, 0)
            data['co2Hex'] = self.valid_assign(self.co2_hex, 'NULL')
            data['co2Dec'] = self.valid_assign(self.co2_dec, 0)
            data['co2Sup'] = self.valid_assign(self.co2_sup, 0)
            data['inverted'] = self.valid_assign(self.inverted, 0)
            data['relatedSource'] = self.valid_assign(self.related_source_id, 'NULL')
            data['ctlCode'] = self.valid_assign(self.ctl_id, 0)
            data['ctlCo2Min'] = self.valid_assign(self.ctl_co2_min, 0)
            data['ctlCo2Max'] = self.valid_assign(self.ctl_co2_max, 0)
            data['ctlDelayOn'] = self.valid_assign(self.ctl_delay_on, 0)
            data['ctlDelayOff'] = self.valid_assign(self.ctl_delay_off, 0)
            data['mldDelayOn'] = self.valid_assign(self.mld_delay_on, 0)
            data['mldDelayOff'] = self.valid_assign(self.mld_delay_off, 0)
            # Validate not to save if source ID/room/type value is invalid
            if data['source'] == 'NULL' or data['room'] == 'NULL' or data['type'] == 'NULL':
                return False
            # Start saving to data by updating or inserting
            if len(query_result) != 0:
                if self.db.update_data(self.table, data) == True:
                    # query_result = self.db.query_data(self.table, data_to_query)
                    return True
                else :
                    return False
            ## Insert new row in "devices" table
            if self.db.insert_data(self.table, data) == True:
                return True
            else:
                return False
        except Exception as err:
            self.logger.error("[data_model] Failed to save data to table data: " + str(err))
            return False

    def delete(self):
        if hasattr(self, 'dev_id'):
            data = {
                'source' : self.source_id,
                'devId' : self.dev_id,
                'slaveId' : 'NULL',
                'channelId' : 'NULL',
                'protocol' : self.protocol,
                'status' : self.status,
                'type' : self.type
            }
        elif hasattr(self, 'slave_id'):
            data = {
                'source' : self.source_id,
                'devId' : 'NULL',
                'slaveId' : self.slave_id,
                'channelId' : 'NULL',
                'protocol' : self.protocol,
                'status' : self.status
            }
        if hasattr(self, 'slave_id'):
            data['channelId'] = self.channel_id
        data_in_database = self.db.query_data(self.table, data)
        if len(data_in_database) != 0:
            if self.db.delete_data(self.table, data) == True :
                return True
            else :
                return False
        else :
            return False

    def __exit__(self):
        self.db.close()