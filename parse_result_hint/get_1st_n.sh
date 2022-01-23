#!/bin/bash

# for monolithic. summary works okay
where=$1

here=$(pwd)
cd ../a_$where/data/poc/dyn
ls -al
echo '>>>>>>>> dynamic'
sudo chown -R cc *
for i in 1 5 10; do
    for c in 0 pf; do
        echo '>>>>>>>>' $c
        head -n$(bc <<< "$i * 1") -q $i/$c/*
        echo
    done
    echo
done
cd $here


echo '>>>>>>>> static'

here=$(pwd)
cd ../a_$where/data/poc/sta
sudo chown -R cc *
for i in 1 5 10; do
    for c in 0 pf; do
        echo '>>>>>>>>' $c
        head -n$(bc <<< "$i * 1") -q $i/$c/*
        echo
    done
    echo
done
cd $here
