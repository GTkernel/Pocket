#!/bin/bash

DEVICE=$(echo "${1:-cpu}" | awk '{print tolower($0)}')

if [[ "$DEVICE" != "cpu" && "$DEVICE" != "gpu" ]]; then
    echo ERROR: First parameter should be either cpu or gpu. Exit.
    exit 1
fi

filename=$(pwd)/perf_$(date +%Y%m%d)_${DEVICE}.log
# filename=$(pwd)/perf_$(date +%Y%m%d_%H%M%S)_${DEVICE}.log
: > $filename

cd a_mobilenetv2
echo 'a_mobilenetv2' >> $filename
echo =============== >> $filename
bash exp_iterate.sh ${DEVICE} >> $filename
cd -

cd a_resnet50
echo 'a_resnet50' >> $filename
echo =============== >> $filename
bash exp_iterate.sh ${DEVICE} >> $filename
cd -

cd a_ssdmobilenetv2_320x320
echo 'a_ssdmobilenetv2_320x320' >> $filename
echo =============== >> $filename
bash exp_iterate.sh ${DEVICE} >> $filename
cd -

cd a_ssdresnet50v1_640x640
echo 'a_ssdresnet50v1_640x640' >> $filename
echo =============== >> $filename
bash exp_iterate.sh ${DEVICE} >> $filename
cd -

cd a_smallbert
echo 'a_smallbert' >> $filename
echo =============== >> $filename
bash exp_iterate.sh ${DEVICE} >> $filename
cd -

cd a_talkingheads
echo 'talking_heads' >> $filename
echo =============== >> $filename
bash exp_iterate.sh ${DEVICE} >> $filename
cd -
