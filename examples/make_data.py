"""Generate synthetic CSVs for the example budgets (illustrative numbers only)."""
import pathlib
import numpy as np

d = pathlib.Path(__file__).parent / 'data'
d.mkdir(exist_ok=True)
g = lambda x, c, w: np.exp(-((x - c) / w) ** 2)
ARCSEC = 180 / np.pi * 3600 / 1e6            # arcsec per microradian
disp = lambda l: (0.015 + 1.5e-5 * (l - 400)) / ARCSEC     # spectrograph dispersion, nm/arcsec
curves = {  # name: (wavelength grid [nm], function of wavelength, column label)
    'al_mgf2_reflectance': (np.arange(350, 1101, 10), lambda l: 0.91 - 0.07 * g(l, 830, 70), 'reflectance'),
    'grating_efficiency':  (np.arange(380, 1051, 10), lambda l: 0.25 + 0.55 * g(l, 580, 330), 'efficiency'),
    'camera_transmission': (np.arange(380, 1101, 20), lambda l: 0.96 - 0.05 * ((l - 650) / 350) ** 2, 'transmission'),
    'detector_qe':         (np.arange(380, 1051, 10), lambda l: 0.92 * g(l, 620, 380), 'qe'),
    # spatial resolution terms, arcseconds (FWHM-equivalent)
    'diffraction':         (np.arange(350, 1101, 25), lambda l: 1.03 * l * 1e-9 / 0.09 * 1e6 * ARCSEC, 'blur_arcsec'),
    'design_residual':     (np.arange(400, 1001, 50), lambda l: (3 + 4 * ((l - 650) / 300) ** 2) * ARCSEC, 'blur_arcsec'),
    'fabrication':         (np.arange(350, 1101, 50), lambda l: 5 * 500 / l * ARCSEC, 'blur_arcsec'),
    'thermal_focus':       (np.arange(350, 1101, 50), lambda l: (2 + 0.004 * (l - 400)) * ARCSEC, 'blur_arcsec'),
    'charge_diffusion':    (np.arange(350, 1101, 25), lambda l: (2 + 5 * ((l - 350) / 700) ** 2) * ARCSEC, 'blur_arcsec'),
    # spatial blur -> resolving power: R = scale / blur, with scale = lambda / dispersion
    'resolving_power':     (np.arange(350, 1101, 50), lambda l: l / disp(l), 'arcsec'),
}
for name, (l, f, col) in curves.items():
    np.savetxt(d / f'{name}.csv', np.c_[l, f(l)], delimiter=',', fmt='%.5g', header=f'wavelength_nm,{col}', comments='')
