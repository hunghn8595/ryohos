from .database_interface import local_storage
from constant import *

class data:

    def __init__(self, sourceid="", devid="", slaveid="", channelid="", devdata="", co2value=0, logger=""):
        self.logger = logger
        if devid != "" and slaveid == "":
            # Assign device ID if Enocean
            self.dev_id = devid
        elif devid == "" and slaveid != "":
            # Assign slave ID if Modbus
            self.slave_id = slaveid
        if channelid != "":
            # Assign channel ID if exists
            self.channel_id = channelid
        # Assign other info if exists
        self.source_id = sourceid
        self.data_dev = devdata
        self.co2_value = co2value
        # Table name
        self.table = "data"
        # Define columns of table
        self.columns = {
            'source': 'text',
            'devId': 'PRIMARY',
            'slaveId': 'PRIMARY',
            'channelId': 'PRIMARY',
            'data': 'text',
            'co2_value': 'int'
        }
        # Initiate database
        self.db = local_storage(logger=logger)
        data_to_get = ()
        if self.data_dev == "":
            data = {'data' : self.data_dev}
            # Handle if device ID is available
            if hasattr(self, 'dev_id') and not hasattr(self, 'slave_id'):
                data = {'devId' : self.dev_id, 'slaveId' : 'NULL', 'channelId' : 'NULL'}
                if hasattr(self, 'channel_id') and self.channel_id != '':
                    data['channelId'] = self.channel_id
                data_to_get = self.db.get_first_row(self.table, data)
                if data_to_get != ():
                    self.data_dev = data_to_get[DT__DATA]
                    self.co2_value = data_to_get[DT__CO2]
                    data ['data'] = self.data_dev
                    data ['co2_value'] = self.co2_value
            # Handle if slave ID is available
            elif hasattr(self, 'slave_id') and not hasattr(self, 'dev_id'):
                data = {'devId' : 'NULL', 'slaveId' : self.slave_id, 'channelId' : 'NULL'}
                if hasattr(self, 'channel_id') and self.channel_id != '':
                    data['channelId'] = self.channel_id
                data_to_get = self.db.get_first_row(self.table, data)
                if data_to_get != ():
                    self.data_dev = data_to_get[DT__DATA]
                    self.co2_value = data_to_get[DT__CO2]
                    data ['data'] = self.data_dev
                    data ['co2_value'] = self.co2_value
            # Handle if only source ID is available
            elif self.source_id != "":
                data = {'source' : self.source_id}
                data_to_get = self.db.get_first_row(self.table, data)
                if data_to_get != ():
                    self.data_dev = data_to_get[DT__DATA]
                    self.co2_value = data_to_get[DT__CO2]
                    data ['data'] = self.data_dev
                    data ['co2_value'] = self.co2_value

    def get_columns(self):
        return self.columns

    def get_table(self):
        return self.table

    def get_data(self):
        data = {}
        if hasattr(self, 'dev_id'):
            data = {'devId' : self.dev_id, 'slaveId' : 'NULL'}
        elif hasattr(self, 'slave_id'):
            data = {'devId' : 'NULL', 'slaveId' : self.slave_id}
        if hasattr(self, 'channel_id') and self.channel_id != '':
            data['channelId'] = self.channel_id
        query_result = self.db.query_data(self.table, data)
        return query_result

    def save(self):
        data = {}
        if hasattr(self, 'dev_id'):
            data = {'devId' : self.dev_id, 'slaveId' : 'NULL'}
        elif hasattr(self, 'slave_id'):
            data = {'devId' : 'NULL', 'slaveId' : self.slave_id}
        if hasattr(self, 'channel_id') and self.channel_id != '':
            data['channelId'] = self.channel_id
        else:
            data['channelId'] = 'NULL'
        # self.logger.debug("[Data Model] Data is " + str(data))
        query_result = self.db.query_data(self.table, data)
        if hasattr(self, 'source_id'):
            data['source'] = self.source_id
        else:
            return False
        data['data'] = self.data_dev
        data['co2_value'] = self.co2_value
        # self.logger.debug("[Data Model] Query result is " + str(query_result))
        # Query to determine row item then update it if exists
        if len(query_result) != 0:
            if self.db.update_data(self.table, data) == True :
                return True
            else :
                return False
        # Insert new row if not exist
        if self.db.insert_data(self.table, data) == True:
            return True
        else:
            return False
        return False

    def delete(self):
        data = {}
        if hasattr(self, 'dev_id'):
            data = {'devId' : self.dev_id, 'slaveId' : 'NULL'}
        elif hasattr(self, 'slave_id'):
            data = {'devId' : 'NULL', 'slaveId' : self.slave_id}
        if hasattr(self, 'source_id') and self.source_id != '':
            data['source'] = self.source_id
        if hasattr(self, 'channel_id') and self.channel_id != '':
            data['channelId'] = self.channel_id
        # Query to determine row item then delete it
        data_in_database = self.db.query_data(self.table, data) 
        if len(data_in_database) != 0:
            if self.db.delete_data(self.table, data) == True :
                return True
            else :
                return False
        else :
            return False

    # def read_data(self):
    def __exit__(self):
        self.db.close()