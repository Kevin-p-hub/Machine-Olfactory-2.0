import time
import spidev
import math
import json
import sys
import gspread
import psutil
import datetime
# from system_info import get_temperature
from oauth2client.service_account import ServiceAccountCredentials

GDOCS_OAUTH_JSON = 'project-1-326122-c7c1f2a881c9.json'
GDOCS_SPREADSHEET_NAME = 'Machine Olfactory 2.0'
FREQUENCY_SECONDS = 2


def login_open_sheet(oauth_key_file, spreadsheet):
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(oauth_key_file,
                                                                       scopes=['https://spreadsheets.google.com/feeds',
                                                                               'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials)
        worksheet = gc.open(spreadsheet).sheet1
        return worksheet
    except Exception as ex:
        print('Unable to login and get spreadsheet. Check OAuth credentials, spreadsheet name, and')
        print('make sure spreadsheet is shared to the client_email address in the OAuth .json file!')
        print('Google sheet login failed with error:', ex)
        sys.exit(1)


print('Logging sensor measurements to {0} every {1} seconds.'.format(GDOCS_SPREADSHEET_NAME, FREQUENCY_SECONDS))
print('Press Ctrl-C to quit.')
worksheet = None

# Assign MCP3008 channel to sensor
channel_mq135 = 4  # Channel 4 for CO2 sensor

# Open SPI bus
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 976000

# Define basic parameters of the sensors
Vin = 5.0
RL_CO2 = 15  # It shows it's adjustable on the datasheet, use 15 first.



# Function to read SPI data from MCP3008 chip
def ReadChannel(channel):
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data


# Function to read sensor connected to MCP3008
## Read sensor mq135
def ReadMq135():
    Vout_CO2 = ReadChannel(channel_mq135)
    return Vout_CO2

## Calibrate mq135 sensor
def MQCalibration_mq135():
    val_CO2 = 0.0
    for i in range(50):  # take 50 samples
        val_CO2 += ReadMq135()
        time.sleep(0.2)
    val_CO2 = val_CO2 / 50
    Sensor_CO2 = val_CO2 * (5.0 / 1023.0)
    Rs_air_CO2 = RL_CO2 * (Vin - Sensor_CO2) / Sensor_CO2
    Ro_CO2 = Rs_air_CO2 / 3.6  # 3.6 was retrieved from the datasheet of MQ135 gas sensor, which is the resistance ratio in fresh air
    print('Ro_CO2 = {0:0.4f} kohm'.format(Ro_CO2))
    return Ro_CO2


def runController(Ro_CO2):
    Vout_CO2_vol = ReadMq135()*(4.9950/1023.0)
    Rs_CO2 = RL_CO2 * (Vin - Vout_CO2_vol)/Vout_CO2_vol
    Rs_Ro_Ratio_CO2 = Rs_CO2 / Ro_CO2
    CO2 = math.exp(((-5 / 582) * (-737 + 200 * (Rs_Ro_Ratio_CO2))))  
    print('CO2 = {0:0.4f} ppm'.format(CO2))
    return CO2


Ro_CO2 = MQCalibration_mq135()

while True:
    if worksheet is None:
        worksheet = login_open_sheet(GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME)

    try:
        CO2_test = runController(Ro_CO2)
        Time = datetime.datetime.now()
        worksheet.append_row((str(Time), CO2_test))

    except:
        print('Append error, logging in again')
        worksheet = None
        time.sleep(FREQUENCY_SECONDS)
        continue
    #print('Wrote a row to {0}'.format(GDOCS_SPREADSHEET_NAME))
    time.sleep(FREQUENCY_SECONDS)
