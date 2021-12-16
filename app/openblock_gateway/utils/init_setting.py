import sys, os
from logging.handlers import RotatingFileHandler
import configparser

def set_constant_config():
    application_configuration = configparser.ConfigParser()
    application_configuration.read("/etc/ryoki_config.ini")
    with open("./configuration.py", "w") as config_file:
    # Writing data to a file
        # System
        config_file.writelines("REBOOT_TRACKFILE = " + \
            str(application_configuration["system"]["REBOOT_TRACKFILE"]) + "\n")
        config_file.writelines("REBOOT_SHORT_DELAY = " + \
            str(application_configuration["system"]["REBOOT_SHORT_DELAY"]) + "\n")
        config_file.writelines("REBOOT_LONG_DELAY = " + \
            str(application_configuration["system"]["REBOOT_LONG_DELAY"]) + "\n")
        config_file.writelines("KEEPING_OUTPUT_TIME = " + \
            str(application_configuration["system"]["KEEPING_OUTPUT_TIME"]) + "\n")
        # Cloud configuration
        config_file.writelines("CERT_PATH = " + \
            str(application_configuration["cloud_configuration"]["CERT_PATH"]) + "\n")
        config_file.writelines("CERTIFICATE_NAME = " + \
            str(application_configuration["cloud_configuration"]["CERTIFICATE_NAME"]) + "\n")
        config_file.writelines("ROOTCA_NAME = " + \
            str(application_configuration["cloud_configuration"]["ROOTCA_NAME"]) + "\n")
        config_file.writelines("PRIVATE_KEY_NAME = " + \
            str(application_configuration["cloud_configuration"]["PRIVATE_KEY_NAME"]) + "\n")
        config_file.writelines("AWS_ENDPOINT = " + \
            str(application_configuration["cloud_configuration"]["AWS_ENDPOINT"]) + "\n")
        config_file.writelines("AWS_TOPIC_PREFIX = " + \
            str(application_configuration["cloud_configuration"]["AWS_TOPIC_PREFIX"]) + "\n")
        config_file.writelines("AWS_DEVICES_SUBSCRIBE_TOPIC_STAGE = " + \
            str(application_configuration["cloud_configuration"]["AWS_DEVICES_SUBSCRIBE_TOPIC_STAGE"]) + "\n")
        config_file.writelines("AWS_CONTROL_SUBSCRIBE_TOPIC_STAGE = " + \
            str(application_configuration["cloud_configuration"]["AWS_CONTROL_SUBSCRIBE_TOPIC_STAGE"]) + "\n")
        config_file.writelines("AWS_TRACKING_SUBSCRIBE_TOPIC_STAGE = " + \
            str(application_configuration["cloud_configuration"]["AWS_TRACKING_SUBSCRIBE_TOPIC_STAGE"]) + "\n")
        config_file.writelines("AWS_REQ_DEV_PUBLISH_TOPIC_STAGE = " + \
            str(application_configuration["cloud_configuration"]["AWS_REQ_DEV_PUBLISH_TOPIC_STAGE"]) + "\n")
        config_file.writelines("AWS_CTL_RESULT_PUBLISH_TOPIC_STAGE = " + \
            str(application_configuration["cloud_configuration"]["AWS_CTL_RESULT_PUBLISH_TOPIC_STAGE"]) + "\n")
        config_file.writelines("AWS_STATUS_PUBLISH_TOPIC_STAGE = " + \
            str(application_configuration["cloud_configuration"]["AWS_STATUS_PUBLISH_TOPIC_STAGE"]) + "\n")
        config_file.writelines("STATUS_PUBLISH_PERIOD = " + \
            str(application_configuration["cloud_configuration"]["STATUS_PUBLISH_PERIOD"]) + "\n")
        config_file.writelines("AWS_DATA_PUBLISH_TOPIC_STAGE = " + \
            str(application_configuration["cloud_configuration"]["AWS_DATA_PUBLISH_TOPIC_STAGE"]) + "\n")
        config_file.writelines("DATA_PUBLISH_PERIOD = " + \
            str(application_configuration["cloud_configuration"]["DATA_PUBLISH_PERIOD"]) + "\n")
        config_file.writelines("SLEEP_TIME_OF_RETRYING_CONNECT = " + \
            str(application_configuration["cloud_configuration"]["SLEEP_TIME_OF_RETRYING_CONNECT"]) + "\n")
        config_file.writelines("SLEEP_TIME_OF_RETRYING_TO_GET_DEVICES = " + \
            str(application_configuration["cloud_configuration"]["SLEEP_TIME_OF_RETRYING_TO_GET_DEVICES"]) + "\n")
        config_file.writelines("NUMBER_OF_RETRY_CONNECTIONS = " + \
            str(application_configuration["cloud_configuration"]["NUMBER_OF_RETRY_CONNECTIONS"]) + "\n")
        config_file.writelines("NUMBER_OF_RETRY_SUBCRIBING = " + \
            str(application_configuration["cloud_configuration"]["NUMBER_OF_RETRY_SUBCRIBING"]) + "\n")
        config_file.writelines("NUMBER_OF_RETRY_PUBLISHING = " + \
            str(application_configuration["cloud_configuration"]["NUMBER_OF_RETRY_PUBLISHING"]) + "\n")
        config_file.writelines("SLEEP_TIME_OF_PUBLISH_CLOUD_DATA = " + \
            str(application_configuration["cloud_configuration"]["SLEEP_TIME_OF_PUBLISH_CLOUD_DATA"]) + "\n")
        config_file.writelines("TRACKING_FILE = " + \
            str(application_configuration["cloud_configuration"]["TRACKING_FILE"]) + "\n")
        config_file.writelines("REQUIRED_CTL_REQ_NO = " + \
            str(application_configuration["cloud_configuration"]["REQUIRED_CTL_REQ_NO"]) + "\n")
        config_file.writelines("REQUIRED_MLD_REQ_NO = " + \
            str(application_configuration["cloud_configuration"]["REQUIRED_MLD_REQ_NO"]) + "\n")
        config_file.writelines("SLEEP_TIME_5M = " + \
            str(application_configuration["cloud_configuration"]["SLEEP_TIME_5M"]) + "\n")
        # Database
        config_file.writelines("DATABASE_NAME = " + \
            str(application_configuration["database"]["DATABASE_NAME"]) + "\n")
        # Logging
        config_file.writelines("LOG_FILE_NAME = " + \
            str(application_configuration["logging"]["LOG_FILE_NAME"]) + "\n")
        # EnOcean
        config_file.writelines("ENO_TTYPATH = " + \
            str(application_configuration["enocean"]["ENO_TTYPATH"]) + "\n")
        config_file.writelines("ENOCEAN_READING_SLEEP_TIME = " + \
            str(application_configuration["enocean"]["ENOCEAN_READING_SLEEP_TIME"]) + "\n")
        config_file.writelines("ENOCEAN_STATUS_TIMEOUT = " + \
            str(application_configuration["enocean"]["ENOCEAN_STATUS_TIMEOUT"]) + "\n")
        config_file.writelines("CO2_928_TIMEOUT = " + \
            str(application_configuration["enocean"]["CO2_928_TIMEOUT"]) + "\n")
        config_file.writelines("ENOCEAN_KEEPING_OUTPUT_TIME = " + \
            str(application_configuration["enocean"]["ENOCEAN_KEEPING_OUTPUT_TIME"]) + "\n")
        # Modbus
        config_file.writelines("MODBUS_TTYPATH = " + \
            str(application_configuration["modbus"]["MODBUS_TTYPATH"]) + "\n")
        config_file.writelines("MODBUS_READING_SLEEP_TIME = " + \
            str(application_configuration["modbus"]["MODBUS_READING_SLEEP_TIME"]) + "\n")
        config_file.writelines("MODBUS_STATUS_TIMEOUT = " + \
            str(application_configuration["modbus"]["MODBUS_STATUS_TIMEOUT"]) + "\n")
        config_file.writelines("MODBUS_KEEPING_OUTPUT_TIME = " + \
            str(application_configuration["modbus"]["MODBUS_KEEPING_OUTPUT_TIME"]) + "\n")
        # FTP
        config_file.writelines("FTP_SERVER_FOLDER_PATH = " + \
            str(application_configuration["ftp"]["FTP_SERVER_FOLDER_PATH"]) + "\n")
    return 1