#!/bin/sh -e

# Function showing instruction to use regswctl.sh script
instruction()
{
    echo "Usage Sample: sh $0 -r -i <DEVICE-ID>"
    echo "Send command message to the ERT-SWC-RM for communication"
    echo "General Options:"
    echo "  -i\tDevice ID of the controller meant to be requested to register. (Obligatory)"
    echo "  -r\tExecuting registration is selected."
    echo "  -t\tExecuting test is selected."
    echo "  -h\tShow help."
    exit 1 # Exit script after showing instruction
}

# Function sends registration UTE message to ERT-SWC-RM device
resgister_ute()
{
    echo "*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*"
    echo "Register UTE to ERT-SWC-RM device whose Device ID is $1"
    python3 ./send_ute_swc.py $1
}

# Function sends command to test ON/OFF status on channels of ERT-SWC-RM device
test_onoff()
{
    echo "*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*"
    echo "Test channels of ERT-SWC-RM device whose Device ID is $1"
    python3 ./test_onoff_swc.py $1
}

# Handle input parameters
show_ins=false
do_registration=false
do_test_channels=false
while getopts "i:rth" opt
do 
    case "$opt" in
        i ) controller_id="$OPTARG";; # Get controller ID from input parameters
        r ) do_registration=true;; # Get requested registration task from input parameters
        t ) do_test_channels=true;; # Get requested testing task from input parameters
        h ) show_ins=true ;; # Show instruction when option is -h
        ? ) instruction ;; # Show instruction in case parameter is non-existent
    esac
done

# Print instruction without warning
if [ "$show_ins" = true ]; then
    instruction
fi
# Print instruction in case input parameters are empty
if [ -z "$controller_id" ]
then
    echo "Some of the required arguments are empty. Device ID must not be empty. Please add argument for -i option."
    instruction
fi
# Print instruction in case input parameters are empty
if [ "$do_registration" = false ] && [ "$do_test_channels" = false ]
then
    echo "Some of the required arguments are empty. Please add option -r or -t or both."
    instruction
fi
# Execute registration
if [ "$do_registration" = true ]; then
    resgister_ute $controller_id
fi
# Execute test channels
if [ "$do_test_channels" = true ]; then
    test_onoff $controller_id
fi

exit 1 # Exit script after finishing requested tasks