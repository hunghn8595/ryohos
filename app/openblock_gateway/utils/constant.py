# Network Info
DEFAULT_NETWORK_IF = "eth0"         # Default interface used for getting MAC address
MAC_ADDR = "08:00:27:8A:00:DF"      # Default MAC address

# AWS Parameters
AWS_THING_NAME = "GW-0800278A00DF"  # Default AWS Thing name, generated from MAC address
AWS_PORT = 8883             # Port on network used for connecting to AWS cloud services

# EnOcean Configuration
ENOCEAN_PROTOCOL = 1        # Value of protocol corresponded to Enocean
ENO_BAUDRATE = 57600        # Baudrate configured for EnOcean communication

# Modbus Configuration
MODBUS_WMB_PROTOCOL = 2     # Value of protocol corresponded to Modbus
MODBUS_SENSOR_PROTOCOL = 3  # Value of protocol corresponded to Modbus
MODBUS_BAUDRATE = 19200     # Baudrate configured for Modbus communication

# Common value of devices data
DEV_STT_CONN = 1
DEV_STT_DISCONN = 2

# Logger Configuration
FORMAT = "%(asctime)s" + "\t%(levelname)s" + "\t%(message)s"    # Format of lines in log file: TIMESTAMP LOG_LEVEL LOG_MESSAGE

# Database Constant
## Define Room table - columns:
RM__ROOM_ID = 0             # Room Id
## Define Devices table - columns:
DV__SC_ID = 0               # Device Source Id
DV__EN_DV_ID = 1            # EnOcean device - Device Id
DV__MB_SV_ID = 2            # Modbus device - Slave Address Id
DV__CHN_ID = 3              # Channel Address Id
DV__PROTOCOL = 4            # Protocol: EnOcean, Modbus
DV__ROOM = 5                # Room contain the device
DV__STATUS = 6              # Current Status of the device: Connected, Disconnected
DV__TYPE = 7                # Type of the device
DV__DIRECTION = 8           # Direction of data: Input (sensor), Output (Controller)
DV__CO2_POS = 9             # Position for CO2 sensor: Indoor, Outdoor
DV__VAL_TYPE = 10           # Sublayer for children coils on the same device (used for GMW83DRP): Temperature, Humidity, CO2
DV__CO2_HEX = 11            # CO2 Hex range used for calculation
DV__CO2_DEC = 12            # CO2 Dec range used for calculation
DV__CO2_SUP = 13            # Complement value for CO2 calculation
DV__INVERTED = 14           # The direction of how device input and output (from 0 -> 1 or 1 -> 0)
DV__RELATED_SC_ID = 15      # The source id that the device relate to
DV__CTL_ID = 16             # Control ID, used for cloud controlling flow
DV__CTLCO2_MIN = 17         # Control lower limit based on CO2
DV__CTLCO2_MAX = 18         # Control upper limit based on CO2
DV__TIME_ON = 19            # Control delay time toggle ON
DV__TIME_OFF = 20           # Control delay time toggle OFF
DV__MLD_TIME_ON = 21        # Control delay time toggle ON in mildew control
DV__MLD_TIME_OFF = 22       # Control delay time toggle OFF in mildew control
### Excluded part from Devices table
DV__EX_PRT_1 = 23           # Extended item 1, not included in the Devices table (command value for output device)
## Define Data table - columns:
DT__SOURCE_ID = 0           # Device Source Id
DT__EN_DV_ID = 1            # EnOcean device - Device Id
DT__MB_SV_ID = 2            # Modbus device - Slave Address Id
DT__CHN_ID = 3              # Channel Address Id
DT__DATA = 4                # Data get from the device
DT__CO2 = 5                 # CO2 value if belong to CO2 sensor

# Categories of device type
SENSOR_DEVICES_LIST = ['co2-928-sensor', 'etb-sic-p-sensor', 'gmd20-sensor', 'gmw83drp-sensor']
CONTROL_MODULES_LIST = ['wmb-ai8-modbus', 'wmb-dio8r-modbus', 'ert-swc-sensor']
CONTROLLED_DEVICES_LIST = ['air-purifier-control', 'uv-c-control', 'other-device-sensor']
TRACKING_DEVICES_LIST = ['air-purifier-control-tracking', 'uv-c-control-tracking', 'other-device-sensor-tracking']

# Control titles
CTL_CLOUD_TTL = 'cloud_control'
CTL_CO2_TTL = 'co2_control'
CTL_INSTANT_TTL = 'instant_control'
CTL_FINAL_TTL = 'final_control'

# Control default values
CONTROL_NEUTRAL = 1         # Control value meant to be ignore instant control flow
CONTROL_ON = 2              # Usual value to turn ON device
CONTROL_OFF = 3             # Usual value to turn OFF device
CONTROL_ON_IMD = 4          # Specific value to immediately turn ON device in instant control flow
CONTROL_OFF_IMD = 5         # Specific value to immediately turn OFF device in instant control flow
CONTROL_OFF_RMV = 7         # Specific value to immediately turn OFF a device in cloud control flow, when stop control this device
VALID_CONTROL = [CONTROL_ON, CONTROL_OFF, CONTROL_ON_IMD, CONTROL_OFF_IMD]

# Control time periods
CONTROL_STEP_DURATION = 5   # Period of small step checkpoints

# Control ID values
CTL_ID_NONE = 0             # No control from cloud
CTL_ID_DS = 1               # Control by desease
CTL_ID_CO2 = 2              # Control by CO2, not depend on cloud
CTL_ID_PMV = 3              # Control by PMV rate
CTL_ID_MLD = 4              # Control by mildew risk

# Control Type ID values, meaning of request from cloud
CTL_TYPE_USUAL = 1          # Usual control request, effected by delay
CTL_TYPE_INSTANT = 2        # Instant control request, no delay
CTL_TYPE_UPDATE = 3         # Remove device from control, turn OFF immediately, no delay

# Control cloud status
CTL_CLD_NONE = 0            # No cloud request from the initialization, or not getting request for more than a minute
CTL_CLD_WAIT = 1            # Waiting for cloud request in range of a period
CTL_CLD_CONT = 2            # Had received request from cloud in range of a period

# Data used for calculation in control by CO2
CO2_IGNORE_VL = -9999       # Calculated CO2 value that would be ignored in controlling
CO2_CALCULATE_INFO = {
    'co2-928-sensor' : {
        'hex_range': 255,
        'dec_range': 2550
    },
    'gmd20-sensor': {
        'hex_range': 10000,
        'dec_range': 2000
    },
    'gmw83drp-sensor': {
        'hex_range': 10000,
        'dec_range': 2000
    }
}