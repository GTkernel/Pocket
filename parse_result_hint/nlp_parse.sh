#!/bin/bash

# for monolithic. summary works okay

echo '>>>>> dynamic: bert'
here=$(pwd)
cd ../a_smallbert/data/poc/dyn
sudo chown -R cc *
for i in 1 5 10; do
    for c in 0 pf; do
        echo $c
        head -n$i -q $i/$c/*
        echo
    done
    echo
done
cd $here

echo '>>>>> static: bert'
here=$(pwd)
cd ../a_smallbert/data/poc/sta
sudo chown -R cc *
for i in 1 5 10; do
    for c in 0 pf; do
        echo $c
        head -n$i -q $i/$c/*
        echo
    done
    echo
done
cd $here

echo '>>>>> dynamic: heads'
cd ../a_talkingheads/data/poc/dyn
sudo chown -R cc *
for i in 1 5 10; do
    for c in 0 pf; do
        echo $c
        head -n$i -q $i/$c/*
        echo
    done
    echo
done
cd $here

echo '>>>>> static: heads'
cd ../a_talkingheads/data/sta
sudo chown -R cc *
for i in 1 5 10; do
    for c in 0 pf; do
        echo $c
        head -n$i -q $i/$c/*
        echo
    done
    echo
done
cd $here