Hook added:

```bash
$ renku aqs
Usage: renku aqs [OPTIONS] COMMAND [ARGS]...

Options:
  -h, --help  Show this message and exit.

Commands:
  leaderboard  Leaderboard based on performance of astroquery requests
  params       List the parameters of astroquery requests

```

Real example:

```bash
$ renku run papermill final-an.ipynb  output.ipynb
Executing: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 13/13 [00:08<00:00,  1.58cell/s]
found annotation: .renku/aq/run-21382.json
{
    "aq_module": "SDSSClass",
    "args": [
        "<SkyCoord (ICRS): (ra, dec) in deg\n    (166.11380792, 38.20883278)>"
    ],
    "kwargs": {
        "data_release": "16",
        "photoobj_fields": "['run', 'rerun', 'camcol', 'field', 'ra', 'dec', 'mode', 'psfFlux_u', 'psfFlux_g', 'psfFlux_r', 'psfFlux_i', 'psfFlux_z', 'psfFluxIvar_u', 'psfFluxIvar_g', 'psfFluxIvar_r', 'psfFluxIvar_i', 'psfFluxIvar_z', 'TAI_u', 'TAI_g', 'TAI_r', 'TAI_i', 'TAI_z', 'objID', 'thingId']",
        "radius": "3arcmin"
    }
}
found annotation: .renku/aq/run-30479.json
{
    "aq_module": "SimbadClass",
    "args": [
        "Mrk 421"
    ],
    "kwargs": {
        "wildcard": "True"
    }
}
```

Note that this is the original final-an.ipynb, and renku plugin intercepts astroquery calls transparently.
