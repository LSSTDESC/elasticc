# NOTE!  This is just a shortcut script that Rob wrote to launch
#  the docker image on his desktop for testing purposes.  It's
#  probably not useful to anybody else.

sudo docker run -d --name 'stream-to-zads' --network host \
     --mount type=bind,source=/data/raknop/temp/alerttest,target=/alerts \
     --mount type=bind,source=/home/raknop/desc/elasticc,target=/elasticc \
     --mount type=bind,source=/home/raknop/desc/stream-to-zads,target=/nightcache \
     --env ELASTICC_COMPRESSION_FACTOR=1 \
     --env ELASTICC_START_TIME=2022-06-08T07:00 \
     --env ELASTICC_ALERT_SERVER=brahms.lbl.gov:9092 \
     --env ELASTICC_ALERT_TOPIC=elasticc-test-only-4 \
     rknop/elasticc-stream-to-zads

#     --env ELASTICC_ALERT_SERVER=public.alerts.ztf.uw.edu:9092 \
#     --env ELASTICC_TOPIC=elasticc-test-only-1 \
