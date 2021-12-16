import sqlite3
import os, sys
sys.path.append(os.path.abspath(os.getcwd() + '/openblock_gateway/utils/'))
from constant import *
from configuration import *
import logging

class local_storage:
    def __init__(self, database_path=DATABASE_NAME, logger=""):
        self.logger = logger
        self.db = sqlite3.connect(database_path)
        self.cur = self.db.cursor()

    # table_name is a string, columns is a dict
    def create_table(self, table_name, columns):
        #check multithread also
        query_command = "CREATE TABLE IF NOT EXISTS " + table_name + " ( "
        primary_key_list = "PRIMARY KEY("
        #check if the table has already existed

        for column in columns:
            if columns[column] == "PRIMARY KEY" :
                query_command = query_command + column + " TEXT, "
                primary_key_list = primary_key_list + column + ", "
            else :
                query_command = query_command + column + " " + columns[column] + ", "
        if len(primary_key_list) > 12:
            primary_key_list = primary_key_list[0:(len(primary_key_list)-2)] # remove ", "
            query_command = query_command + primary_key_list +  "));"
        else:
            query_command = query_command[0:(len(query_command)-2)] + ");" # remove ", "

        try:
            self.cur.execute(query_command)
            self.db.commit()
        except Exception as e:
            self.logger.error ("[Database]create_table - error: " + str(e))
            return False
        return True

    def close(self) :
        try:
            self.db.close()
        except Exception as e:
            self.logger.error ("[Database]close - error: " + str(e))
            return False
        return True

    def update_data(self, table_name, data):
        query_command = "UPDATE " + table_name + " SET "
        condition = " WHERE "
        names_of_id_field = []
        for field in data:
            if field.find('Id') == -1:
                query_command = query_command + field + " = '" + str(data[field]) + "', "
            else :
                names_of_id_field.append(field)
        if query_command[(len(query_command)-2):] == ", ":
            query_command = query_command[0:(len (query_command)-2)] # remove ", "
        query_command = query_command + " WHERE "
        for field_name in names_of_id_field:
            query_command = query_command + field_name + " = '" + str(data[field_name]) + "' AND "
        if query_command[(len(query_command)-4):] == "AND ":
            query_command = query_command[0:(len (query_command)-4)] # remove "AND "

        try:
            self.cur.execute(query_command)
            self.db.commit()
        except Exception as e:
            self.logger.error ("[Database]update_data - error: " + str(e))
            return False
        return True


    def insert_data(self, table_name, data) :
        query_command = "INSERT INTO " + table_name + " ( "
        for field in data:
            query_command = query_command + field + ", "
        query_command = query_command[0:(len (query_command)-2)] # remove ", "
        query_command = query_command + " ) VALUES ( "
        for field in data:
            query_command = query_command + " '" + str(data[field]) + "', "

        query_command = query_command[0:(len (query_command)-2)] # remove ", "
        query_command = query_command + " ) "

        try:
            self.cur.execute(query_command)
            self.db.commit()
        except Exception as e:
            self.logger.error ("[Database]insert_data - error: " + str(e))
            return False
        return True

    # def pop_data(model):
    def query_data(self, table_name, data={}) :
        query_command = "SELECT *"
        query_command = query_command + " FROM " + table_name
        if not (data == "" or data == {}):
            query_command = query_command + " WHERE "
            for field in data:
                query_command = query_command + field + " = '" + str(data[field]) + "' AND "
        if query_command[(len(query_command)-4):] == "AND ":
            query_command = query_command[0:(len (query_command)-4)] # remove "AND "

        try:
            self.cur.execute(query_command)
            self.db.commit()
            result = self.cur.fetchall()
            return result
        except Exception as e:
            self.logger.error ("[Database]query_data - error: " + str(e))
            return []


    def delete_data(self, table_name, data) :
        query_command = "DELETE FROM " + table_name + " WHERE "
        for field in data:
            query_command = query_command + field + " = '" + str(data[field]) + "' AND "

        query_command = query_command[0:(len (query_command)-4)] # remove "AND "\
        try:
            self.cur.execute(query_command)
            self.db.commit()
        except Exception as e:
            self.logger.error ("[Database]delete_data - error: " + str(e))
            return False
        return True

    def get_first_row(self, table_name, data):
        query_command = "SELECT *"
        # query_command = query_command + ")"
        query_command = query_command + " FROM " + table_name + " WHERE "
        for field in data:
            query_command = query_command + field + " = '" + str(data[field]) + "' AND "

        query_command = query_command[0:(len (query_command)-4)] # remove "AND "
        query_command = query_command  + "LIMIT 1"
        try:
            self.cur.execute(query_command)
            self.db.commit()
            result = self.cur.fetchall()
            if len(result) != 0:
                return result[0]
            else:
                return ()
        except Exception as e:
            self.logger.error ("[Database]get_first_row - error: " + str(e))
            return ()

        # Tells the database class more about the table columns in the database