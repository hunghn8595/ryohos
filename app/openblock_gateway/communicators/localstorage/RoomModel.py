from .database_interface import local_storage
from constant import *

class room:
    # options can be new or get 
    def __init__(self, id="", options="new", logger=""):
        self.id = id
        self.table = "rooms"
        self.columns =  {'roomId' : 'PRIMARY KEY'}
        self.db = local_storage(logger=logger)
        # if options == "get" :
        #     data = {'id' : self.id}
        #     data_to_get = self.db.get_first_row(self.table, data)
        #     if len(data_to_get) != 0:
        #         self.id = data_to_get[0][0]
        #         # self.data_dev = data_to_get[0][1]
        #         data ['data'] = self.data_dev
        #         self.db.delete_data(self.table, data)

    def get_columns(self):
        return self.columns

    def get_table(self):
        return self.table

    def get_data(self):
        data = {}
        if hasattr(self, 'id') and self.id != "":
            data = {'roomId' : self.id}
            query_result = self.db.query_data(self.table, data)
        else :
            query_result = self.db.query_data(self.table)
        return query_result

    def save(self):
        data = {'roomId' : self.id}
        query_result = self.db.query_data(self.table, data)
        if len(query_result) != 0:
            return True

        if self.db.insert_data(self.table, data) == True:
            return True
        else:
            return False
        return 0

    def delete(self):
        data = {'roomId' : self.id}
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