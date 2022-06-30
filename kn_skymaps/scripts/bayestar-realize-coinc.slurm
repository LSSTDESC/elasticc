#!/bin/bash
#SBATCH --qos=shared
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=deep1018@illinois.edu
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --cpus-per-task=30
#SBATCH --mem=32G
#SBATCH --output=./ELASTICC_KN_SKYMAPS/bayestar-realize-coincs.out
#SBATCH --error=./ELASTICC_KN_SKYMAPS/bayestar-realize-coincs.err

source /global/cfs/cdirs/lsst/groups/TD/setup_td_dev.sh

# COINCs for the Bulla model
srun bayestar-realize-coincs ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_B19_MASS_EJECTA_INJ.xml \
	-o ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_B19_MASS_EJECTA_COINC.xml \
	--reference-psd elasticc-test-data/psd-o4.xml \
	--detector H1 L1 V1 K1 \
	--measurement-error gaussian-noise \
	--snr-threshold 4.0 \
	--net-snr-threshold 8.0 \
	--min-triggers 2 \
	--seed 1234 -j 29

# COINCs for the Kasen model
srun bayestar-realize-coincs ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_K17_MASS_EJECTA_INJ.xml \
	-o ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_K17_MASS_EJECTA_COINC.xml \
	--reference-psd elasticc-test-data/psd-o4.xml \
	--detector H1 L1 V1 K1 \
	--measurement-error gaussian-noise \
	--snr-threshold 4.0 \
	--net-snr-threshold 8.0 \
	--min-triggers 2 \
	--seed 1234 -j 29
