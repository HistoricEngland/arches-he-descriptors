# Arches HE Descriptors

An Arches extension for generating Historic England resource display names,
descriptions and map popups from graph-specific YAML rules.

## Documentation

Start here for installation and integration. Each supporting document owns a
different topic:

| Document | Use it for |
| --- | --- |
| [Configuration guide](./docs/USER_GUIDE.md) | Admin workflow, YAML fields, rules, filters, operations and examples |
| [Implementation guide](./docs/IMPLEMENTATION_GUIDE.md) | Service internals, API contracts, limitations and testing |

## Requirements

- Python >=3.10, subject to the supported Python versions of your Arches release.
- Arches >=7.6.17, <7.7.0.
- The database, search services and front-end tooling required by your Arches
  project.

These package constraints come from [pyproject.toml](./pyproject.toml); they are
not a claim that every newer Python release has been tested.

## Integrating into an existing Arches project

Run management commands from the host project's directory containing
`manage.py`, using its environment and settings.

### 1. Install the package

#### From PyPI

Install Arches HE Descriptors from
[PyPI](https://pypi.org/project/arches-he-descriptors/) into your host project's
Python environment:

```bash
python -m pip install arches-he-descriptors
```

If the host project manages dependencies in `pyproject.toml`, add the package to
its existing `[project]` dependencies and install using the project's normal
dependency workflow:

```toml
dependencies = [
    # Keep the project's existing dependencies.
    "arches-he-descriptors",
]
```

For reproducible deployments, pin a published version using
`arches-he-descriptors==<published-version>`, replacing the placeholder with your
chosen release. The distribution name is `arches-he-descriptors`; the Python
module and Django application name remain `arches_he_descriptors`.

Installing the package does not configure the host project, apply migrations or
register the function. Continue with steps 2-6 below.

#### From a local checkout or Git

For development or installing directly from source, use a local checkout:

```bash
pip install -e /path/to/arches_he_descriptors
```

Alternatively, add a Git dependency to the host project's `[project]`
dependencies, selecting a branch, tag or preferably a commit you have verified:

```toml
dependencies = [
    # Keep the project's existing dependencies.
    "arches-he-descriptors @ git+https://github.com/HistoricEngland/arches-he-descriptors.git@<verified-ref>",
]
```

Replace `<verified-ref>` before installing. Keep the host's Arches version within
the [requirements](#requirements); do not lower dependency constraints merely to
make an incompatible environment install.

### 2. Configure application discovery

Add `arches_he_descriptors` to the existing `INSTALLED_APPS` and
`ARCHES_APPLICATIONS` collections. Preserve all existing entries.

Append the package locations to the existing Arches settings:

```python
DATATYPE_LOCATIONS.append("arches_he_descriptors.datatypes")
FUNCTION_LOCATIONS.append("arches_he_descriptors.functions")
SEARCH_COMPONENT_LOCATIONS.append("arches_he_descriptors.search_components")
```

### 3. Include the URLs before catch-all routes

In the host project's URL configuration, add:

```python
path("", include("arches_he_descriptors.urls")),
```

Import `path` and `include` from `django.urls`. Place this include before any
catch-all application include: otherwise descriptor API requests can be
intercepted by that application.

The package URL configuration also includes Arches core URLs. Check the host's
include ordering rather than assuming this is a descriptor-only URL module.
The registered endpoints are documented in the
[API reference](./docs/IMPLEMENTATION_GUIDE.md#api-reference).

### 4. Apply migrations and register the function

```bash
python manage.py migrate
python manage.py fn register --source /path/to/arches_he_descriptors/arches_he_descriptors/functions/arches_he_descriptors.py
python manage.py fn list
```

Adjust the registration path to the checkout or installed package. For a PyPI
installation, locate the function file using the same Python environment as the
host project:

```bash
python -c "import arches_he_descriptors; from pathlib import Path; print(Path(arches_he_descriptors.__file__).parent / 'functions' / 'arches_he_descriptors.py')"
```

Use the printed absolute path as the registration command's `--source` argument.
In this repository's application container, the checkout path is:

```bash
python manage.py fn register --source /web_root/arches_he_descriptors/arches_he_descriptors/functions/arches_he_descriptors.py
```

Migrations create the configuration table; they do not register the Arches
function. Confirm that **Arches HE Descriptors** appears in the function list.

### 5. Assign and configure descriptors

In the graph designer, assign **Arches HE Descriptors** as the resource model's
primary descriptor function, replacing the previous primary descriptor
assignment. Keep exactly one primary descriptor function assigned.

Create the graph's configuration in Django admin under **Display descriptor
graph configs**, following the
[admin workflow](./docs/USER_GUIDE.md#managing-configurations).
Use the [Monument example](./docs/USER_GUIDE.md#monument-name-example) as a starting
point, adapting it to the destination graph and vocabulary.

For display names, turn on **Enabled** in the function's Display Name tab.
Internally this is `descriptor_types.name.show_prn=True`: it enables YAML
rendering, rather than automatically adding a primary reference number.
The YAML format decides whether a reference number appears. When this flag is
explicitly `False`, the function returns the existing stored name.

The function maps Arches `name`, `description` and `map_popup` to the
`display_name`, `display_description` and `map_popup` configuration sections.
See [section storage](./docs/USER_GUIDE.md#descriptor-sections) and
[function behaviour](./docs/IMPLEMENTATION_GUIDE.md#arches-function-behaviour),
including the `Undefined` fallback.

Publish the graph after configuring its function assignment. Saving YAML does
not regenerate stored resource descriptors. Regenerate existing descriptors
through the host project's Arches workflow; the name integration tests exercise
`Resource.save_descriptors(descriptors=("name",))`.

### 6. Build and start the host project

Use the host project's normal front-end build and deployment workflow. If it
provides the same development scripts as this repository:

```bash
npm install
npm run build_development
python manage.py runserver
```

Run the npm commands in the directory containing the host's `package.json`.
`runserver` is for development, not production deployment. See the
[Arches deployment documentation](https://arches.readthedocs.io/en/stable/deployment/)
and the [API deployment caveats](./docs/IMPLEMENTATION_GUIDE.md#deployment-caveats).

### Docker integration

For an existing containerised project, install the package in the image and
mount its checkout into each service that needs it (application, livereload and
webpack). Adapt service names and paths to your compose layout; the former
Mariner-specific instructions are consolidated here.

For a build context containing the checkout, a Dockerfile can include:

```dockerfile
ARG ARCHES_HE_DESCRIPTORS_PATH=./arches_he_descriptors
COPY ${ARCHES_HE_DESCRIPTORS_PATH} /web_root/arches_he_descriptors
RUN pip install -e '/web_root/arches_he_descriptors[dev]'
```

For development, the corresponding compose volume is:

```yaml
volumes:
  - ../../arches_he_descriptors:/web_root/arches_he_descriptors
```

The source path is relative to the compose file. Rebuild the image after changing
its installation steps, then run migrations and function registration inside the
host application container as described above.

## Developing this repository

You can develop this repository as an Arches project, or install it in editable
mode in an existing development environment:

```bash
pip install -e '/path/to/arches_he_descriptors[dev]'
```

### Included arches-containers configuration

The [.ac_arches_he_descriptors configuration](./.ac_arches_he_descriptors/)
expects the checkout directory to use underscores:

```bash
git clone https://github.com/HistoricEngland/arches-he-descriptors.git arches_he_descriptors
```

Install Docker and
[arches-containers](https://pypi.org/project/arches-containers/), then run from
the workspace containing the checkout:

```bash
act import -p arches_he_descriptors
act activate -p arches_he_descriptors
act up
```

Review the configuration's sibling checkout/data mounts and Arches branch before
starting; provide those directories and keep the selected Arches version within
the package constraints. Once setup and webpack builds finish, open
<http://localhost:8002> or run `act view`.

## Testing

See [Running tests](./docs/IMPLEMENTATION_GUIDE.md#running-tests) for commands,
environment requirements, coverage boundaries and the offline Monument fixtures.
The app and project function suites must run separately and sequentially.

## Licence

The project includes the GNU Affero General Public License version 3 in
[LICENSE](./LICENSE).
