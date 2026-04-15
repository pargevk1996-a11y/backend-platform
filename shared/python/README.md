# shared-python

Shared contracts and utilities for backend-platform services.

The package version is the compatibility boundary between services. Production deployments should
install this package as a versioned internal artifact, for example `shared-python==0.1.0`, instead
of relying on a mutable `PYTHONPATH` checkout during rolling deploys.
