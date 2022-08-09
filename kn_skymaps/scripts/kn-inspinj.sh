#!/usr/bin/env bash
python kn-rapid-inspinj.py \
  --input ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_B19_MASS_EJECTA_MAP.csv \
  --output ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_B19_MASS_EJECTA_INJ.xml \
  --sample-process-table process-tables.xml

python kn-rapid-inspinj.py \
  --input ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_K17_MASS_EJECTA_MAP.csv \
  --output ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_K17_MASS_EJECTA_INJ.xml \
  --sample-process-table process-tables.xml
