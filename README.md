# Arches HE Descriptors

An Arches extension for generating resource display names, descriptions and map
popups from graph-specific YAML rules.

Any organisation can configure it to suit its resource models, terminology and
descriptor policies; it is not limited to Historic England data or workflows.

## Why use this?

A resource can have several names, no name, or useful identifying information
spread across different cards. This function lets you express the descriptor
policy in configuration rather than relying only on tile order or changing code:

- Prefer a Primary name, then Statutory or Original, before taking another name.
- Combine fields from different cards in the same descriptor.
- Try another rule when required information is missing, or supply a default.
- Control reference-number placement and apply text transformations.

These descriptors help users recognise resources in search results, report
titles, editor headings and map popups. A synthesised label may be shared by many
resources; include an appropriate reference number when users need to distinguish
them. A readable descriptor is not itself a guaranteed unique identifier.

See the [configuration recipes](./docs/USER_GUIDE.md#configuration-recipes) for
preferred-name selection and a period/type fallback for unnamed monuments.

## Requirements

- Python >=3.10, within the versions supported by your Arches release.
- Arches >=7.6.17, <7.7.0.
- The database, search services and front-end tooling required by your host
  Arches project.

These package constraints come from [pyproject.toml](./pyproject.toml); they do
not imply that every newer Python version has been tested.

## Integrating into an existing Arches project

Use the host project's Python environment for installation and all Python
commands. Run every `python manage.py ...` command below from the host project's
directory containing `manage.py`, using that project's settings and database,
not this extension's standalone development settings.

Run npm commands from the directory containing the host's `package.json`.
In Docker, run Python commands in the host application container and npm
commands in the service with the host's front-end tooling, often the webpack
container. See [Docker integration](#docker-integration) for checkout mounts.

### 1. Install the package

Choose **one** installation source below. Do not install a PyPI candidate and
then replace it with a Git dependency unless that switch is intentional.
Installation does not configure the host project or register the function;
continue with steps 2-9.

#### From PyPI, after publication

The PyPI commands below apply only once `1.0.0rc1` has been published and is
visible on the [project's release page](https://pypi.org/project/arches-he-descriptors/1.0.0rc1/).
Until then, use a verified Git revision or local checkout instead.

Select the release candidate explicitly:

```bash
python -m pip install arches-he-descriptors==1.0.0rc1
```

If the host manages dependencies in `pyproject.toml`, add the candidate to its
existing `[project]` dependencies and use the host's normal installation
workflow. Preserve every other dependency and its compatible Arches constraint:

```toml
[project]
dependencies = [
    # Keep the host project's existing dependencies here.
    "arches-he-descriptors==1.0.0rc1",
]
```

Do not add a second `[project]` table or replace the existing dependency array.
See the [candidate release notes](./releases/1.0.0rc1.md) for changes,
limitations and publication checks. An unpinned installation normally selects
stable releases rather than release candidates.

#### From Git or a local checkout

For a Git installation, select a branch, tag or preferably a commit you have
verified:

```bash
python -m pip install "arches-he-descriptors @ git+https://github.com/HistoricEngland/arches-he-descriptors.git@<verified-ref>"
```

Replace `<verified-ref>` before running the command. A moving branch is not
equivalent to the published release candidate. If the host manages dependencies
in `pyproject.toml`, use this same Git dependency string in its existing
`[project].dependencies` array **instead of** the PyPI version pin.

For a local checkout, install it in editable mode:

```bash
python -m pip install -e /path/to/arches_he_descriptors
```

The distribution name is `arches-he-descriptors`; the Python module and Django
application name remain `arches_he_descriptors`.

### 2. Configure application discovery

In the host's settings, insert `"arches_he_descriptors"` into the existing
`INSTALLED_APPS` collection. Preserve the host application, Django/Arches apps
and all other extensions; keep `"arches.app"` last where the host uses that
ordering for template precedence.

If the host explicitly maintains an `ARCHES_APPLICATIONS` collection, add
`"arches_he_descriptors"` to it without replacing any existing entries. Do not
replace the whole collection with `("arches_he_descriptors",)`.

In the current Arches implementation, the extension's `AppConfig` declares
`is_arches_application = True`, so Arches discovers its function location from
`INSTALLED_APPS`. Additional manual `FUNCTION_LOCATIONS` entries are not needed
for this function.

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


### 4. Run database migrations

Run the following command to apply any database migrations required by this app:

```bash
python manage.py migrate
```

### 5. Register the function

```bash
python manage.py fn register --source /path/to/arches_he_descriptors/arches_he_descriptors/functions/arches_he_descriptors.py
python manage.py fn list
```

Adjust the registration path to the checkout or installed package. If you
installed the package via pip, you can locate and register the function in one
step using the host project's Python environment:

```bash
FUNCTION_SOURCE="$(python -c 'from pathlib import Path; import arches_he_descriptors; print(Path(arches_he_descriptors.__file__).resolve().parent / "functions" / "arches_he_descriptors.py")')" &&
python manage.py fn register --source "$FUNCTION_SOURCE"
```

In this repository's application container, the checkout path is:

```bash
python manage.py fn register --source /web_root/arches_he_descriptors/arches_he_descriptors/functions/arches_he_descriptors.py
```

Migrations create the configuration table; they do not register the Arches
function. Confirm that **Arches HE Descriptors** appears in the function list.


### 6. Install and build front-end dependencies

From the directory containing your `your_project/package.json`:

```bash
npm install
npm run build_development
```

Use the host's normal build script if it differs from `build_development`.
For a containerised development setup, use its webpack service rather than
starting a second build or watcher unnecessarily.

### 7. Start your Arches project

```bash
python manage.py runserver
```

`runserver` is for development, not production deployment. See the
[Arches deployment documentation](https://arches.readthedocs.io/en/stable/deployment/)
and the [API deployment caveats](./docs/IMPLEMENTATION_GUIDE.md#deployment-caveats).


### 8. Assign and configure descriptors

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
not regenerate stored resource descriptors.

Before applying configuration to existing resources, use **Test Display
Descriptor** and **Check** in Django admin with representative resource UUIDs.
Test each configured descriptor section, inspect the output and errors, then
save the configuration. The function editor displays saved YAML read-only; it
is not the configuration editor.

### 9. Regenerate existing descriptors

Previewing YAML does not update stored descriptors or search results. After
saving and testing the configuration and publishing the graph, use Arches'
graph-scoped indexing command to recalculate existing resource descriptors and
update their search entries.

**This is a data-changing operation, not a preview.** Back up the database and
follow the host's search-index recovery and maintenance procedures. The command
below recalculates **all three** descriptor types for **every resource in the
selected graph**. Missing or invalid section configuration can produce
`Undefined`, so check all three sections before proceeding.

First confirm the available flags in your host's Arches version:

```bash
python manage.py es --help
```

Replace `<graph-uuid>` with the resource model's graph UUID, not a resource UUID:

```bash
python manage.py es index_resources_by_type \
    --resource_type "<graph-uuid>" \
    --recalculate-descriptors \
    --clear_index true
```

`--clear_index true` clears the selected graph's existing search entries before
rebuilding them; those resources may temporarily disappear from search.
Schedule the operation appropriately and monitor its output and server logs.
It does not request a full-database `reindex_database` operation.

After completion, reopen representative resources and check their stored names,
descriptions and map popups, then confirm the expected values in search results.
If output is `Undefined`, correct the configuration and test it again before
repeating the regeneration.


### Docker integration

For an existing containerised project, install the package in the image and
mount its checkout into each service that needs it (application, livereload and
webpack). Adapt service names and paths to your compose layout.

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
python -m pip install -e '/path/to/arches_he_descriptors[dev]'
```

Editable mode lets you change Python source without reinstalling after each
edit. Follow the host's normal process for restarting Python services and
rebuilding front-end assets.

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


## License

This project is licensed under the GNU AGPLv3. See the LICENSE file for details.

---

For more information on deploying your Arches project, see the [Arches Deployment Guide](https://arches.readthedocs.io/en/stable/deployment/).
