#!/bin/bash


while : ; do
    lineno=$(ps aux | grep exp_iterate.sh | wc -l)
    if [[ "$lineno" = "1" ]]; then
        sleep 10
        break
    fi
    sleep 60
done

bash exp_iterate.sh
