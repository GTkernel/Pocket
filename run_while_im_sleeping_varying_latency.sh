#!/bin/bash

# filename=$(pwd)/temp3.log
filename=$(pwd)/varying_policy.log


# cd a_mobilenetv2
# echo 'a_mobilenetv2' > $filename
# echo =============== >> $filename
# bash exp_varying_policy.sh >> $filename
# cd -

# cd a_resnet50
# echo 'a_resnet50' >> $filename
# echo =============== >> $filename
# bash exp_varying_policy.sh >> $filename
# cd -

# cd a_smallbert
# echo 'a_smallbert' >> $filename
# echo =============== >> $filename
# bash exp_varying_policy.sh >> $filename
# cd -

# cd a_ssdresnet50v1_640x640
# echo 'a_ssdresnet50v1_640x640' >> $filename
# echo =============== >> $filename
# bash exp_varying_policy.sh >> $filename
# cd -

cd a_ssdmobilenetv2_320x320
echo 'a_ssdmobilenetv2_320x320' >> $filename
echo =============== >> $filename
bash exp_varying_policy.sh >> $filename
cd -

cd a_talkingheads
echo 'talking_heads' >> $filename
echo =============== >> $filename
bash exp_varying_policy.sh >> $filename
cd -
