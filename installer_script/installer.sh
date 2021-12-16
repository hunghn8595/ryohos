#!/bin/sh -e

echo "==============================================================="
echo "Installing Iot Gateway version 1.0 Firmware"

# Handle input parameters
is_dev_env=false
firmware_only=false
while getopts ":df" opt
do
    case "$opt" in
        d ) is_dev_env=true;; # Handle to deploy for development environment, separated from product environment
        f ) firmware_only=true;; # Only update firmware
    esac
done

LIB_HOLDER=/home/lib
# Can skip updating libs by adding option -f
if [ "$firmware_only" = false ];
then
    echo "Installing/Updating linux environment"
    sudo apt update
    sudo apt install tar
    sudo apt install sqlite3=3.27.2-3+deb10u1
    sudo apt install awscli
    sudo apt install python3
    sudo apt install python3-pip
    sudo pip3 install -U urllib3 requests
    # Prepare directory to store pip lib packages temporarily
    sudo mkdir $LIB_HOLDER
    sudo mkdir $LIB_HOLDER/pyserial
    sudo mkdir $LIB_HOLDER/pymodbus
    sudo mkdir $LIB_HOLDER/AWSIotPythonSDK
    sudo mkdir $LIB_HOLDER/crc8
    sudo mkdir $LIB_HOLDER/boto3
    sudo mkdir $LIB_HOLDER/awscli
    sudo mkdir $LIB_HOLDER/shutils
    # Install pip packages
    echo y | sudo TMPDIR=$LIB_HOLDER/pyserial pip3 install --cache-dir=$LIB_HOLDER/pyserial --build $LIB_HOLDER/pyserial pyserial==3.5 --user
    echo y | sudo TMPDIR=$LIB_HOLDER/pymodbus pip3 install --cache-dir=$LIB_HOLDER/pymodbus --build $LIB_HOLDER/pymodbus pymodbus==2.5.1 --user
    echo y | sudo TMPDIR=$LIB_HOLDER/AWSIotPythonSDK pip3 install --cache-dir=$LIB_HOLDER/AWSIotPythonSDK --build $LIB_HOLDER/AWSIotPythonSDK AWSIotPythonSDK==1.4.9 --user
    echo y | sudo TMPDIR=$LIB_HOLDER/crc8 pip3 install --cache-dir=$LIB_HOLDER/crc8 --build $LIB_HOLDER/crc8 crc8==0.1.0 --user
    echo y | sudo TMPDIR=$LIB_HOLDER/boto3 pip3 install --cache-dir=$LIB_HOLDER/boto3 --build $LIB_HOLDER/boto3 boto3 --user
    echo y | sudo TMPDIR=$LIB_HOLDER/awscli pip3 install --cache-dir=$LIB_HOLDER/awscli --build $LIB_HOLDER/awscli awscli --user
    echo y | sudo TMPDIR=$LIB_HOLDER/shutils pip3 install --cache-dir=$LIB_HOLDER/shutils --build $LIB_HOLDER/shutils shutils --user
    rm -rf $LIB_HOLDER
    echo "Finished installing/updating linux environment"
fi

# This script would be used to install the application of the gateway
if [ -d "/usr/local/bin/ob_iot_gw" ]
then
    sudo rm -rf /usr/local/bin/ob_iot_gw
fi
sudo mkdir /usr/local/bin/ob_iot_gw
# Prepare directory for camera images containing
sudo mkdir /var/tmp
sudo mkdir /var/tmp/ftpserver

# Extract source to system folder
echo "Extracting files"
sudo tar -xvf ./source_zip.tar -C /usr/local/bin/ob_iot_gw
if [ "$is_dev_env" = true ];
then
    sudo cp ./dev_env_supplement/ryoki_config.ini /etc
else
    sudo cp ./ryoki_config.ini /etc
fi
echo "Finished extracting"

echo "Configuring for executing source files"
# Change owner to root
sudo chown -R root:root /usr/local/bin/ob_iot_gw/app/__init__.py
sudo chown -R root:root /etc/rc.local
sudo chown -R root:root /etc/ryoki_config.ini

# Modify rc.local to run the ob_iot_gw application in background at bootup
sudo chmod 700 /etc/rc.local

echo "Modifying rc-local file"
rc_file='/etc/rc.local'
n=1
del_num=0
anchor=0
anchor_cont="# Ryoki_IoT_GW_app"
end_file="exit 0"
while read line; do
    # Seek for the mark of GW app if installed
    if [ "$line" = "$anchor_cont" ];
    then
        anchor=$n
    fi
    # Seek for the end line of bash file: "exit 0"
    # If exists then remove it also, this would be added again later
    if [ "$line" = "$end_file" ];
    then
        del_num=1
    fi
    n=$((n+1))
done < $rc_file
# Start remove old content from the line of "Ryoki" if exists
if [ "$anchor" != 0 ];
then
    del_num=$((n-anchor-del_num+2))
fi
tail -n $del_num $rc_file | wc -c | xargs -I {} truncate $rc_file -s -{}
# Update new content to rc.local file
cat ./rc_mod.txt >> $rc_file

# Grant permission for execution
sudo chmod 500 /usr/local/bin/ob_iot_gw/app/__init__.py
sudo chmod 500 /etc/rc.local
sudo chmod 500 /etc/ryoki_config.ini

echo "aws configure."
aws configure set aws_access_key_id AKIA2HKKIZNOC3IZUEPY
aws configure set aws_secret_access_key 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
if [ "$is_dev_env" = true ];
then
    aws configure set default.region ap-southeast-1
else
    aws configure set default.region ap-northeast-1
fi
echo "add to crontab"
echo '*/1 * * * * /usr/bin/python3 /opt/gateway_application/camera/camera.py' > cron.conf
crontab cron.conf

echo "Firmware version 1.0 has been updated sucessfully."