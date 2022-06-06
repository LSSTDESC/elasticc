# Creating a map between `SIM_MODEL_INDEX` and the `KN_INDEX` for B19 and K17 models
- For B19, for example,
```
grep SED: $PLASTICC_ROOT/model_libs_updates/SIMSED.BULLA-BNS-M2-2COMP/SED.INFO | awk '{ print $3"\t"$4"\t"$5"\t"$6 }' | tee B19-SIM-TEMPLATE-INDEX-KN-INDEX.map
```
- For K17, for example
```
grep SED: $PLASTICC_ROOT/model_libs/SIMSED.KN-K17/SED.INFO | awk '{ print $3"\t"$4"\t"$5"\t"$6 }' | tee K17-SIM-TEMPLATE-INDEX-KN-INDEX.map
```
- Then converted to JSON for ease of use (included in the repo).


# Steps to create skymaps from KN simulations
Following is brief description of the content of the `scripts` directory. These are used to create skymaps from the SNANA KN header files. The procedure is that mentioned in [Chatterjee et. al (2022)](https://doi.org/10.1093/mnras/stab3023). The skymaps are created using BAYESTAR described in [Singer and Price (2016)](https://doi.org/10.1103/PhysRevD.93.024013).
- First step: map the ejecta mass parameters to binary parameters. Done using `mej_to_masses.py`. See `mej_to_masses.slurm` for CLI.
- Put the binary values in a LIGO light weight table. Done using `kn-inspinj.py` (does not require slurm). See `kn-inspinj.sh`.
- The PSD used for the skymaps involved following BNS inspiral ranges: H1, L1 ~ 180Mpc, V ~ 115 Mpc, K ~ 25 Mpc.
- Run `bayestar-realize-coincs` on the binaries. This tells 1) binaries that are detected 2) provides the SNR time-series. This is done in `bayestar-realize-coinc.slurm`. The result is LIGO LW coinc XML file, which is also converted to an sqlite database for easy querying. It is worth pointing out that the number of KNs which are jointly detected in this exercise is a small subset of the total number of KN in the SNANA header files.
The reason is twofold: 1) In converting from ejecta mass to component mass, we only consider $M_{\text{ej}} < 0.05 M_{\odot}$. This is because we restrict to the SLY equation of state which does not allow for larger ejecta masses. We use an empirical relation based on relation by Dietrich and Ujevic (2017) as implemented in the `gwemlightcurves` project. 2) Out of those lightcurves that satisfy the previous condition, not all pass the detection threshold of a minium of 4 in single detector and 8 in the network they are detected in, which at least involves two detectors.
- Run `bayestar-localize-coincs` on the recovered SNR time-series. This is done in `run-bayestar-localize.slurm`.
- Output files have filenames as: `0.fits`, `1.fits` etc. The number corresponds to the row number in the `sim_inspiral` table of the output XML/sqlite produced. To join the GW and EM parameters i.e. the sqlite and SNANA FITS headers, perform a join on the `source` column of the `sim_inspiral` table and the `SNID` column of the header.
Code snippet
```
>>> # load the SNANA header files for, say, B19 models
>>> import glob, sqlite3
>>> import pandas as pd
>>> from astropy.table import Table
>>> fnames = glob.glob('TRAINING_SAMPLES/ELASTICC_TRAIN_KN_B19/*HEAD*FITS.gz')
>>> header_files = []
>>> for fname in fnames:
...     header_files.append(Table.read(fname, format='fits').to_pandas())
>>> df_lightcurves = pd.concat(header_files, ignore_index=True)

>>> # load the GW coincidence properties
>>> with sqlite3.connect('ELASTICC_KN_SKYMAPS/ELASTICC_TRAIN_KN_B19_MASS_EJECTA_COINC.sqlite') as conn:
...    df_gw = pd.read_sql("SELECT * FROM sim_inspiral", conn)
>>> # create a SNID column in the GW dataframe for joining
>>> df_gw['SNID'] = df_gw.source.apply(lambda x: x.strip('GAL')).astype(int)
>>> df_lightcurves['SNID'] = df_lightcurves.SNID.astype(int)
>>> df_coinc = df_gw.merge(df_lightcurves, on='SNID')
>>> df_coinc.loc[:, ['SNID', 'simulation_id', 'SIM_RA', 'SIM_DEC']].head()
       SNID  simulation_id      SIM_RA    SIM_DEC
0   1335095              0   70.512573 -39.288109
1  64081858              1  308.673981 -42.913502
2   2653700              2  113.815804 -46.176556
3  12352119              3  336.922913 -30.235270
4  85508186              4  171.113525 -23.298241
```
In the above snippet, the value of the `simulation_id` corresponding to the skymap file name corresponding to the `SNID`. For example, `ELASTICC_KN_SKYMAPS/0.fits` corresponds to the SNANA object with `SNID=1335095`. Finally, the filenames are renamed tagging them using the SNID and the MJD from the SNANA headers. This is done using `skymap-postproc.py`.
