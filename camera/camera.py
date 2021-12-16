import os
import ntpath
import logging
import pathlib

import boto3
import requests
import time
import urllib.request
import shutil
from datetime import datetime
import datetime
import json
from logging.handlers import RotatingFileHandler
from botocore.exceptions import NoCredentialsError

#カメラのパス
pathroot = "/opt/gateway_application/camera"
#FTPのパス
path_folder_server = '/var/tmp/ftpserver/'
path_log = pathroot+'/logUploadFile.csv'
path_fileTemp = pathroot + '/tmp/'
format_log = '%(asctime)s %(levelname)s %(message)s'
file_extension = '.jpg'
bucketS3 = "ryoki.monitor.images"

def init_logging():
    """
    ログを書き込む機能
    :return: logger
    """
    logging.basicConfig(filename=path_log,\
                        level=logging.DEBUG,\
                         format=format_log)
    logger = logging.getLogger(path_log)
    my_handler = RotatingFileHandler(path_log, mode='a', maxBytes=5*1024*1024,
                                      backupCount=2, encoding=None, delay=0)
    formatter = logging.Formatter(format_log)
    my_handler.setFormatter(formatter)
    logger.addHandler(my_handler)
    return logger

def delete_folder_null(listFolder,path):
    """
    空フォルダがあれば削除する
    :param listFolder:
    :param path:
    """
    for i in listFolder:
        if not os.listdir(path+"/"+i):
            os.rmdir(path+"/"+i)

def checkInternetRequests(url='https://www.google.com/', timeout=3):
    """
    インターネットに接続するかどうか確認する
    :param url:
    :param timeout:
    :return: boolean
    """
    try:
        r = requests.head(url, timeout=timeout)
        return True
    except requests.ConnectionError as ex:
        logger(ex)
        return False

def upload_image_to_S3(file_name, folder_path):
    headers = {'Content-Type':'application/json'}
    data = {"fileName" : file_name}
    response = requests.put('https://api.prooptiment.jp/api/v1/gw/presignedurl', headers=headers, data=json.dumps(data))
    response_data = response.json()
    if "isSuccess" in response_data.keys():
        if response_data["isSuccess"]:
            if"data" in response_data.keys():
                header_up_file = {'Content-type': 'image/jpeg'}
                put_image_url = response_data["data"]["presignedUrl"]
                with open(folder_path + file_name, 'rb') as file:
                    response = requests.put(put_image_url, data=file, headers=header_up_file)
                if response.status_code == 200:
                    return True
                return False
            else:
                return False
        else:
            logger.error("issuccess is false")
            print ("issuccess is false")
            return False
    else:
        logger.error("issuccess is not found")
        print ("issuccess is not found")
        return False

# Initiate logging module
logger = init_logging()
#tempファイルを存在しない場合tempファイルを作成する
#temp名がログファイルの最終日付
if not os.listdir(path_fileTemp):
   lastmodified = os.stat(path_log).st_mtime
   date = datetime.datetime.fromtimestamp(lastmodified)
   formatDate = date.strftime("%Y-%m-%d")
   a = pathlib.Path(path_fileTemp+formatDate+".txt")
   a.touch()
#tempファイルを存在する場合：　temp名を取得して、tempファイルの日付+7days<=現在日付
#　＝>tempファイル名を削除して、ログファイルを作成
else:
    dirTemp = os.listdir(path_fileTemp)
    fileTemp = [f for f in dirTemp if os.path.isfile(os.path.join(path_fileTemp, f))]
    nameFileTemp = os.path.splitext(os.path.basename(fileTemp[0]))[0]
    datetmp = datetime.datetime.strptime(nameFileTemp, "%Y-%m-%d")
    today = datetime.datetime.today()
    plusDay = datetmp + datetime.timedelta(days=7)
    if plusDay <= today:
        os.remove(path_log)
        os.rename(path_fileTemp+fileTemp[0], path_fileTemp+today.strftime("%Y-%m-%d") + ".txt")
        f = open(path_log, 'w')
        f.close()

#FTPフォルダの存在をチェックする
if os.path.exists(path_folder_server) != True:
    print("Folder FTP root not exist")
    exit()

count = 0
#インターネットを確認する
while checkInternetRequests() != True:
    time.sleep(3)
    count += 1
    if count == 3:
        exit()

getDirName = os.listdir(path_folder_server)
dir = [f for f in getDirName if os.path.isdir(os.path.join(path_folder_server, f))]
for i in dir:
    os.chdir(path_folder_server + i)
    pth = os.getcwd()
    files = os.listdir(pth)
    dircamera = [f for f in files if os.path.isdir(os.path.join(pth, f))]
    if len(dircamera) != 0:
        #空のフォルダを削除する
        delete_folder_null(dircamera,pth)
        dircamera = [f for f in files if os.path.isdir(os.path.join(pth, f))]
        #フォルダを存在しない場合はif分をbreakする
        if len(dircamera) == 0:
            break
        dirca = max(dircamera, key=os.path.getctime)
        #カメラフォルダに遷移する
        os.chdir(pth+"/"+dirca)
        cameraPath = os.getcwd()
        #最新のファイル名を取得する
        files = os.listdir(cameraPath)
        paths = [os.path.join(cameraPath, basename) for basename in files]
        if len(paths) != 0:
            image = max(paths, key=os.path.getctime)
            today = datetime.datetime.today().strftime("%Y%m%d%H%M%S")
            nameImageCamera = cameraPath+"/"+i+"_"+today+file_extension
            rename_file = os.rename(image, nameImageCamera)
            fileUPload: str = i + "_" + today + file_extension
            checkCode = upload_image_to_S3(fileUPload, cameraPath + "/")
            time.sleep(5)
            #カメラのフォルダを削除する
            if checkCode == True:
                for i in dircamera:
                    if os.listdir(pth + "/" + i):
                        shutil.rmtree(pth + "/" + i)