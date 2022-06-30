#!/bin/bash
#SBATCH --qos=debug
#SBATCH --constraint=haswell
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=deep1018@illinois.edu
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=16G
#SBATCH --output=./ELASTICC_KN_SKYMAPS/mej_to_masses.out
#SBATCH --error=./ELASTICC_KN_SKYMAPS/mej_to_masses.err

source /global/cfs/cdirs/lsst/groups/TD/setup_td_dev.sh

python mej_to_masses.py \
  --input-files "/global/cfs/cdirs/lsst/www/DESC_TD_PUBLIC/ELASTICC/TRAINING_SAMPLES/ELASTICC_TRAIN_KN_K17/*HEAD*FITS.gz" \
  --output "${HOME}/github/uiucsn/retraining-rapid/kn-rapid/utils/ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_K17_MASS_EJECTA_MAP.csv" \
  --chirp-mass-ul 1.5 \
  --chirp-mass-ll 0.8 \
  --mass-ratio-ul 1.0 \
  --mass-ratio-ll 0.5 \
  --component-mass-ll 1.0 \
  --component-mass-ul 2.1 \
  --sed-model "K17" \
  --sim-index-mapping-file "${HOME}/github/uiucsn/retraining-rapid/kn-rapid/utils/K17-SIM-TEMPLATE-INDEX-KN-INDEX.JSON" \
  --eos-name "SLY" \
  --ejecta-mass-threshold 0.05 \
  --maxiter 2000 \
  --tolerance 1e-3 \
  --ligo-gpstime-format \
  --pool 40 \
  --verbose

python mej_to_masses.py \
  --input-files "/global/cfs/cdirs/lsst/www/DESC_TD_PUBLIC/ELASTICC/TRAINING_SAMPLES/ELASTICC_TRAIN_KN_B19/*HEAD*FITS.gz" \
  --output "${HOME}/github/uiucsn/retraining-rapid/kn-rapid/utils/ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_B19_MASS_EJECTA_MAP.csv" \
  --chirp-mass-ul 1.5 \
  --chirp-mass-ll 0.8 \
  --mass-ratio-ul 1.0 \
  --mass-ratio-ll 0.5 \
  --component-mass-ll 1.0 \
  --component-mass-ul 2.1 \
  --sed-model "B19" \
  --sim-index-mapping-file "${HOME}/github/uiucsn/retraining-rapid/kn-rapid/utils/B19-SIM-TEMPLATE-INDEX-KN-INDEX.JSON" \
  --eos-name "SLY" \
  --ejecta-mass-threshold 0.05 \
  --maxiter 2000 \
  --tolerance 1e-3 \
  --ligo-gpstime-format \
  --pool 40 \
  --verbose

