
* first you need to build a folder structure manually.

* for pockets, first half is for dynamics and the otehrs are static.

* For pocket to remove warmup.
read all lines after 10 from file
first 3 files are valid for all
e.g. for pagefault, n=3
read first 3 files, from 11th line.
```
for file in *; do
    tail -n +10 $file
    echo
done > ~/yolov3-tf2-new/temp
```

* For monolithic
read all lines from file
first n*3 files are valid
e.g. for pagefault, n=3
read first 9 pf file
```
for file in *; do
    cat $file
    echo
done > ~/yolov3-tf2-new/temp
```