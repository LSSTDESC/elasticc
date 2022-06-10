Maintainer: Rob Knop (raknop@lbl.gov)

The Dockerfile builds an image that should stream ELAsTiCC alerts
(original alerts with embedded diaObject and diaSource).

It's set up on NERSC Spin (producton m1727, namespace elasticc-alerts,
workload elasticc-alert-streamer).  It's configured with four
environment variables:

* `ELASTICC_ALERT_SERVER` -- the server to stream to
* `ELASTICC_ALERT_TOPIC` -- the topic to stream to
* `ELASTICC_COMPRESSION_FACTOR` -- number of simulated days to stream each day
* `ELASTICC_START_TIME` -- the date that the campaign starts.  (The code
     will look at the current time and decide which range of simulated days
     to stream based on this.)

It needs to mount three external volumes:

* `/alerts` -- the directory to find the alerts.  Has subdirectories
  (currently, needs to be updated for real elasticc)
  `ELASTICC_ALERTS_TEST_EXTRAGALACTIC-SNIa/ALERTS`,
  `ELASTICC_ALERTS_TEST_EXTRAGALACTIC-nonIa/ALERTS`, and
  `ELASTICC_ALERTS_TEST_GALACTIC`.
* `/elasticc` -- A checkout of the elasticc github archive.  Needs to
  have subdirectory `alert_schema` with the alert schema.
* `/nightcache` -- Can be a persistent volume instead of a bind mount.
  The code dumps a list of simulated nights its streamed to a file in,
  this directory, so that it won't redo if the code is restarted.


