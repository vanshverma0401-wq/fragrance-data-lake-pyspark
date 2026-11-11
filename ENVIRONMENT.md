# Environment and verification scope

The original academic execution and this public reconstruction are separate.
The exact original managed-cluster dependency lock was not recovered, so the
public requirements file must not be described as that original environment.

## Small local checks

The November 2026 synthetic example and saved-result contract checks were run
on macOS arm64 with **CPython 3.12.14**, **NumPy 2.3.5**, **Pandas 2.2.3** and
**pytest 8.4.1**. SQLite comes from the Python standard library. These exact test
dependencies are in [requirements-test.txt](requirements-test.txt).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

The [CI workflow](.github/workflows/checks.yml) uses Python 3.12 and these test
dependencies. It checks the public package and synthetic behavior, not AWS or
the historical large-data run. Its current outcome is visible in GitHub Actions;
the presence of the YAML file is not a passing-run claim.

## Spark and visuals

The existing [requirements.txt](requirements.txt) describes broader dependency
ranges for plotting and the PySpark reconstruction. Fresh chart regeneration
and Spark execution were not performed as part of the small November 2026
reliability extension. The Spark job also requires a separately configured JDK
and Spark runtime. Before using it, record:

```bash
python --version
java -version
spark-submit --version
python -m pip freeze
```

Select compatible Python/JDK/Spark releases using the documentation for that
Spark version. Do not infer a validated cluster configuration from the local
fixture tests. Source acquisition and rights remain governed by
[DATA_AND_USAGE.md](DATA_AND_USAGE.md).
