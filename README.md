# SoftPack Builder


[![pypi](https://img.shields.io/pypi/v/softpack-builder.svg)](https://pypi.org/project/softpack-builder/)
[![python](https://img.shields.io/pypi/pyversions/softpack-builder.svg)](https://pypi.org/project/softpack-builder/)
[![Build Status](https://github.com/wtsi-hgi/softpack-builder/actions/workflows/dev.yml/badge.svg)](https://github.com/wtsi-hgi/softpack-builder/actions/workflows/dev.yml)
[![codecov](https://codecov.io/gh/wtsi-hgi/softpack-builder/branch/main/graphs/badge.svg)](https://codecov.io/github/wtsi-hgi/softpack-builder)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](https://www.contributor-covenant.org/version/2/1/code_of_conduct)



SoftPack Builder provides services for building SoftPack environments.


* Documentation: <https://wtsi-hgi.github.io/softpack-builder>
* GitHub: <https://github.com/wtsi-hgi/softpack-builder>
* PyPI: <https://pypi.org/project/softpack-builder/>
* Free software: MIT


## Features

* Delivers cross-platform software packaging environments for reproducible research.
* Includes integrated management and monitoring of build flows using [Prefect][].
* Supports distributed and parallel builds using [Dask][] for seamless scalability.

## Installation

### Stable release

To install SoftPack Builder, run this command in your
terminal:

``` console
$ pip install softpack-builder
```

This is the preferred method to install SoftPack Builder, as it will always install the most recent stable release.

If you don't have [pip][] installed, this [Python installation guide][]
can guide you through the process.

### From source

The source for SoftPack Builder can be downloaded from
the [Github repo][].

You can either clone the public repository:

``` console
$ git clone git://github.com/wtsi-hgi/softpack-builder
```

Or download the [tarball][]:

``` console
$ curl -OJL https://github.com/wtsi-hgi/softpack-builder/tarball/master
```

Once you have a copy of the source, you can install it with:

``` console
$ pip install .
```

[pip]: https://pip.pypa.io
[Python installation guide]: http://docs.python-guide.org/en/latest/starting/installation/
[Github repo]: https://github.com/wtsi-hgi/softpack-builder
[tarball]: https://github.com/wtsi-hgi/softpack-builder/tarball/master
[Dask]: https://www.dask.org
[Prefect]: https://www.prefect.io


## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [altaf-ali/cookiecutter-pypackage](https://altaf-ali.github.io/cookiecutter-pypackage) project template.

SoftPack mascot and logo courtesy of <a href="https://www.vecteezy.com/free-vector/cartoon">Cartoon Vectors by Vecteezy</a>.
