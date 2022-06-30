#!/bin/bash
#SBATCH --qos=shared
#SBATCH --constraint=haswell
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=deep1018@illinois.edu
#SBATCH --time=6:00:00
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=32G
#SBATCH --output=ELASTICC_KN_SKYMAPS/bayestar-localize-coincs.out
#SBATCH --error=ELASTICC_KN_SKYMAPS/bayestar-localize-coincs.err

source /global/cfs/cdirs/lsst/groups/TD/setup_td_dev.sh

export OMP_NUM_THREADS=64

# B19 skymaps
# srun bayestar-localize-coincs ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_B19_MASS_EJECTA_COINC.xml
# K17 skymaps
srun bayestar-localize-coincs ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_K17_MASS_EJECTA_COINC.xml
