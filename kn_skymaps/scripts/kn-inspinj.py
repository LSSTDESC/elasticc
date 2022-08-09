from argparse import ArgumentParser

from ligo.lw import ligolw, lsctables
from gwpy import table, time
import numpy as np

parser = ArgumentParser(
    "Construct an inj.xml for bayestar-realize-coinc"
)
parser.add_argument("-i", "--input", required=True,
    help="CSV output table of mej_to_masses.py"
)
parser.add_argument("-o", "--output", required=True,
    help="Output table in LIGOLW XML format"
)
parser.add_argument("--gpsstart", type=int, default=1000000000,
    help="Assign a gpstime start and step time for injections."
    " Not required. Only used if input is missing a `first_detection` entry."
)
parser.add_argument("--gpsstep", type=int, default=200,
    help="Time step between injetions. Not required. "
    "Only used if input is missing a `first_detection` entry."
)
parser.add_argument("--sample-process-table", default='process-tables.xml',
    help="Sample LIGOLW process and process_params table."
)

args = parser.parse_args()

# create and write a fiducial process and
# process_params table for bayestar-realize-coincs
#process_table = lsctables.ProcessTable()
#process_params_table = lsctables.ProcessParamsTable()
process_table = table.Table.read(args.sample_process_table,
                                 tablename='process')
process_params_table = table.Table.read(
    args.sample_process_table, tablename='process_params'
)
process_table.write(
    args.output, format='ligolw', tablename='process',
    append=True, overwrite=True, ilwdchar_compat=False
)
process_params_table.write(
    args.output, format='ligolw', tablename='process_params',
    append=True, overwrite=True, ilwdchar_compat=False
)
# load the input table
data_table = table.Table.read(args.input)
# various quantities that go into the XML files
num_inj = len(data_table)
process_id = [lsctables.ProcessID(0) for ii in range(num_inj)]
waveform = ['TaylorF2threePointFivePN'] * num_inj
try:
    geocent_end_time = data_table['first_detection']
    geocent_end_time -= 7200  # subtract an ad-hoc delay
except KeyError:
    # fiducial gpstime for the injections
    geocent_end_time = [args.gpsstart + args.gpsstep*ii for ii in range(num_inj)]
geocent_end_time_ns = np.zeros(num_inj)

h_end_time = geocent_end_time.copy()
h_end_time_ns = geocent_end_time_ns.copy()
l_end_time = geocent_end_time.copy()
l_end_time_ns = geocent_end_time_ns.copy()
g_end_time = geocent_end_time.copy()
g_end_time_ns = geocent_end_time_ns.copy()
t_end_time = geocent_end_time.copy()
t_end_time_ns = geocent_end_time_ns.copy()
v_end_time = geocent_end_time.copy()
v_end_time_ns = geocent_end_time_ns.copy()

end_time_gmst = [
    time.Time(time.from_gps(ii)).jd for ii in geocent_end_time
]
source = [f'GAL{ii}' for ii in data_table['snid']]

mass1 = data_table['mass1'].data
mass2 = data_table['mass2'].data

mchirp = data_table['chirp_mass'].data
eta = mass1 * mass2 / (mass1 + mass2)**2
distance = data_table['distance'].data
longitude = data_table['ra'] / 180. * np.pi
latitude = data_table['dec'] / 180. * np.pi

inclination = np.arccos(data_table['costheta'])
# for kasen models, the costheta column is cannibalized to
# add lanthanide fraction of the ejecta.
if np.all(np.isnan(inclination)):
    inclination = np.arccos(np.random.uniform(-1, 1, num_inj))

coa_phase = np.random.uniform(0, 2*np.pi, num_inj)
polarization = np.random.uniform(0, 2*np.pi, num_inj)

psi0 = np.zeros(num_inj)
psi3 = np.zeros(num_inj)
alpha = np.zeros(num_inj)
alpha1 = np.zeros(num_inj)
alpha2 = np.zeros(num_inj)
alpha3 = np.zeros(num_inj)
alpha4 = np.zeros(num_inj)
alpha5 = np.zeros(num_inj)
alpha6 = np.zeros(num_inj)
beta = np.zeros(num_inj)
spin1x = np.zeros(num_inj)
spin1y = np.zeros(num_inj)
spin1z = np.zeros(num_inj)
spin2x = np.zeros(num_inj)
spin2y = np.zeros(num_inj)
spin2z = np.zeros(num_inj)

theta0 = np.zeros(num_inj)
phi0 = np.zeros(num_inj)
f_lower = 20 * np.ones(num_inj)
f_final = np.zeros(num_inj)

numrel_mode_min = np.zeros(num_inj)
numrel_mode_max = np.zeros(num_inj)
numrel_data = [" "] * num_inj
amp_order = [-1] * num_inj
taper = ['TAPER_NONE'] * num_inj

bandpass = np.zeros(num_inj)
simulation_id = [lsctables.SimInspiralID(ii) for ii in range(num_inj)]

eff_dist_h = distance.copy()
eff_dist_l = distance.copy()
eff_dist_g = distance.copy()
eff_dist_t = distance.copy()
eff_dist_v = distance.copy()

new_table = table.Table(
    [table.Column(waveform, dtype='str', name='waveform'),
     table.Column(geocent_end_time, name='geocent_end_time', dtype='int'),
     table.Column(geocent_end_time_ns, name='geocent_end_time_ns', dtype='int'),
     table.Column(h_end_time, name='h_end_time', dtype='int'),
     table.Column(g_end_time, name='g_end_time', dtype='int'),
     table.Column(l_end_time, name='l_end_time', dtype='int'),
     table.Column(v_end_time, name='v_end_time', dtype='int'),
     table.Column(t_end_time, name='t_end_time', dtype='int'),
     table.Column(h_end_time_ns, name='h_end_time_ns', dtype='int'),
     table.Column(g_end_time_ns, name='g_end_time_ns', dtype='int'),
     table.Column(l_end_time_ns, name='l_end_time_ns', dtype='int'),
     table.Column(v_end_time_ns, name='v_end_time_ns', dtype='int'),
     table.Column(t_end_time_ns, name='t_end_time_ns', dtype='int'),
     table.Column(end_time_gmst, name='end_time_gmst', dtype='int'),
     table.Column(source, name='source', dtype='str'),
     table.Column(mass1, name='mass1', dtype='float'),
     table.Column(mass2, name='mass2', dtype='float'),
     table.Column(mchirp, name='mchirp', dtype='float'),
     table.Column(eta, name='eta', dtype='float'),
     table.Column(distance, name='distance', dtype='float'),
     table.Column(eff_dist_g, name='eff_dist_g', dtype='float'),
     table.Column(eff_dist_h, name='eff_dist_h', dtype='float'),
     table.Column(eff_dist_l, name='eff_dist_l', dtype='float'),
     table.Column(eff_dist_v, name='eff_dist_v', dtype='float'),
     table.Column(eff_dist_t, name='eff_dist_t', dtype='float'),
     table.Column(coa_phase, name='coa_phase', dtype='float'),
     table.Column(longitude, name='longitude', dtype='float'),
     table.Column(latitude, name='latitude', dtype='float'),
     table.Column(inclination, name='inclination', dtype='float'),
     table.Column(polarization, name='polarization', dtype='float'),
     table.Column(psi0, name='psi0', dtype='float'),
     table.Column(psi3, name='psi3', dtype='float'),
     table.Column(spin1x, name='spin1x', dtype='float'),
     table.Column(spin1y, name='spin1y', dtype='float'),
     table.Column(spin1z, name='spin1z', dtype='float'),
     table.Column(spin2x, name='spin2x', dtype='float'),
     table.Column(spin2y, name='spin2y', dtype='float'),
     table.Column(spin2z, name='spin2z', dtype='float'),
     table.Column(f_final, name='f_final', dtype='float'),
     table.Column(f_lower, name='f_lower', dtype='float'),
     table.Column(alpha, name='alpha', dtype='float'),
     table.Column(alpha1, name='alpha1', dtype='float'),
     table.Column(alpha2, name='alpha2', dtype='float'),
     table.Column(alpha3, name='alpha3', dtype='float'),
     table.Column(alpha4, name='alpha4', dtype='float'),
     table.Column(alpha5, name='alpha5', dtype='float'),
     table.Column(alpha6, name='alpha6', dtype='float'),
     table.Column(beta, name='beta', dtype='float'),
     table.Column(theta0, name='theta0', dtype='float'),
     table.Column(phi0, name='phi0', dtype='float'),
     table.Column(amp_order, name='amp_order', dtype='int'),
     table.Column(numrel_mode_min, name='numrel_mode_min', dtype='int'),
     table.Column(numrel_mode_max, name='numrel_mode_max', dtype='int'),
     table.Column(numrel_data, name='numrel_data', dtype='str'),
     table.Column(bandpass, name='bandpass', dtype='int'),
     table.Column(taper, name='taper', dtype='str'),
     table.Column(process_id, name='process_id', dtype='object'),
     table.Column(simulation_id, name='simulation_id', dtype='object')]
)

new_table.write(args.output, format='ligolw', tablename='sim_inspiral',
                append=True, overwrite=True)
