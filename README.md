# Arches HE Descriptors

This is an Arches extension app that provides descriptor functions used by Historic England for use with their Arches-based heritage inventory systems.

## Requirements

- Python 3.10+ (Check the Arches python requirements and match your Python version)
- Arches >=7.6.17, <7.7.0

## Running Tests

The descriptor unit tests cover configuration parsing, rendering rules and
transformations. A graph-backed test imports the Arches `Resource Test Model`,
attaches the HE descriptor function, writes tile data, and verifies the generated
resource descriptor. Run them inside the application container:

```bash
docker exec archeshedescriptors sh -lc 'cd /web_root/arches_he_descriptors && python manage.py test --noinput --verbosity=2 --settings=arches_he_descriptors.tests.settings arches_he_descriptors.tests.test_display_descriptor_operations arches_he_descriptors.tests.test_display_descriptor_engine arches_he_descriptors.tests.test_display_descriptor_service arches_he_descriptors.tests.test_display_descriptor_graph'
```

There are two test locations, which must be run in separate invocations:

- [App tests](arches_he_descriptors/tests/) contain operations, engine, service and
  graph regression tests. Their settings expect an Arches checkout alongside this
  project (`../arches`, mounted at `/web_root/arches` in Docker), providing the core
  `tests.base_test` helpers.
- [Project function tests](tests/function_tests/) contain Monument fixture,
  graph setup and resource/function integration tests. They use the project's
  own `tests` package. Combining both groups under one settings module can cause
  a collision with the core Arches `tests` package.

Run the two groups sequentially: their database-backed tests use the same default
test database name. PostgreSQL/PostGIS must be available for database-backed
tests, and Elasticsearch must also be available for the Monument test runner.
Use `tests.test_settings_for_docker` for Monument tests inside Docker; the
non-Docker `tests.test_settings` explicitly uses Elasticsearch on `localhost`,
which is not the separate Elasticsearch container.

Current coverage is **64 test methods**, excluding individual `subTest` cases:

| Module | Test methods |
| --- | ---: |
| [Operations](arches_he_descriptors/tests/test_display_descriptor_operations.py) | 13 |
| [Engine](arches_he_descriptors/tests/test_display_descriptor_engine.py) | 13 |
| [Service](arches_he_descriptors/tests/test_display_descriptor_service.py) | 6 |
| [Graph regressions](arches_he_descriptors/tests/test_display_descriptor_graph.py) | 3 |
| [Graph fixture preparation](tests/function_tests/test_graph_fixture.py) | 7 |
| [Monument graph setup](tests/function_tests/test_monument_graph_setup.py) | 3 |
| [Monument resource/function integration](tests/function_tests/test_monument_resource_setup.py) | 19 |
| **Total** | **64** |

HTTP API endpoint tests have not yet been added. The service and function tests
do not verify URL routing, HTTP status codes or JSON response contracts.

Operation tests live in
[test_display_descriptor_operations.py](arches_he_descriptors/tests/test_display_descriptor_operations.py),
separate from engine rule/filter tests. They cover every `OperationType` and
assert that the example cases and dispatch handlers match the enum, plus option,
missing-value and length-boundary cases. Engine tests cover missing/default values,
subfield agreement/ambiguity, priority fallback and combined subfield filters.
These unit tests do not load St Bernard's or require a database.
Run just the operation tests with:

```bash
docker exec archeshedescriptors sh -lc 'cd /web_root/arches_he_descriptors && python manage.py test --noinput --verbosity=2 --settings=arches_he_descriptors.tests.settings arches_he_descriptors.tests.test_display_descriptor_operations'
```

The Monument graph setup tests load CIDOC CRM and the required photo widget,
register Arches HE Descriptors, and prepare a descriptor-only copy of the
Arches 6.2 graph export for Arches 7.6 before importing and publishing it.
Graph/card text and widget labels are converted to language-keyed objects
(for example, `{"en": "Monument"}`), preserving existing translations and nulls.
Node names remain plain strings, as required by Arches 7.6.
The three source-specific non-descriptor functions and the unsupported
`bngcentrepoint` nodegroup (including its card, widget, and incident edges)
are explicitly excluded; the source JSON is not modified.
The source-specific report template and configuration are replaced with the
built-in default report template and an empty report configuration.
The source HE primary descriptor assignment is replaced with Arches HE Descriptors.
The original descriptor nodegroups and templates are preserved, and HE name
rendering is enabled with `show_prn=True`. Tests that exercise rendering must also
provide resource tiles and a `DisplayDescriptorGraphConfig`.

```bash
docker exec archeshedescriptors sh -lc 'cd /web_root/arches_he_descriptors && python manage.py test --noinput --verbosity=2 --settings=tests.test_settings_for_docker tests.function_tests'
```

These tests use a separate Django test database; they do not depend on functions
registered manually in the application database.
They do not test the excluded spatial functions or Generate Unique References.

The Monument resource setup tests also load the saved
[St Bernard's bulk disambiguated API response](tests/fixtures/pkg/business_data/st_bernards_monument.bulk_disambiguated.json)
after publishing the graph. The first-pass
[fixture loader](tests/function_tests/resource_fixture.py) creates one resource
with its 13 names, four descriptions and system identifiers. Strings use Arches
7.6 English tile values (`{"en": {"value": "...", "direction": "ltr"}}`), and the
primary reference number is numeric. Source resource/tile IDs and legacy ID are
retained. Tile sortorder is assigned from the saved arrays, starting at zero per
section; this is deterministic test ordering, not recovered source sortorder.

The shared Monument test setup loads the offline Django fixture
[st_bernards_concepts.json](tests/fixtures/pkg/reference_data/st_bernards_concepts.json)
before graph import/resource creation. It contains the 11 concept values populated
in the loaded sections and their five collections: Name Use Type, Currency Type,
Description Type, Languages and Metatypes. Source concept/value/collection IDs and
English preferred labels are retained. Membership was checked against the source
instance's public collection endpoints; relation IDs are test-local, and legacy
concept identifiers use the concept UUIDs rather than unknown source legacy IDs.
This is a minimal test subset, not a full vocabulary or concept-scheme export.

The resource loader stores concept **value** UUIDs, leaving unpopulated concept
fields null, and verifies loaded value metadata and collection membership before
creating records. Missing or inconsistent vocabulary raises an explicit error.
All other resource sections are still omitted and listed in the loader result;
no related resources are created. Tests do not contact the source St Bernard's
Arches instance; the saved fixtures are used offline. Database-backed tests still
connect to PostgreSQL, and the Monument runner creates and deletes test search
indices in Elasticsearch.
The loader writes ResourceInstance/TileModel records atomically and rejects
duplicate loads; it does not run Resource/Tile save hooks, index the resource, or
copy source display descriptors. It is test scaffolding, not a general API-data
importer. The saved API response is left unchanged.
The resource tests attach a `DisplayDescriptorGraphConfig` for the first Primary
name (falling back to the first name) and primary reference number, then call
`Resource.save_descriptors` through the registered HE function and verify the
generated name is persisted. Service tests also exercise description priority
`Summary|Full|FIRST` against real concept-backed tiles. Description priority is
tested with an inline service configuration, not the function's description path.
Rule-order tests verify two required name-use subfield filters fail before the
third rule succeeds, including subfield alias formatting and transformation.
Another test verifies every filtered rule fails before a final catch-all block
(`{"rule": [], "format": "Monument: no matching name use type"}`) supplies the
descriptor. Both scenarios verify the name is persisted through the installed
HE function.

The fixture preparation tests can also run without Django or a database:

```bash
python -m unittest tests.function_tests.test_graph_fixture
```

## Installing for Development

For development purposes, you can treat this app as a standard Arches project. Either use the instructions for developing an Arches project or use the arches-containers configuration included in this repository.

- **For development (standard):**

  ```bash
  pip install -e '/path/to/arches_he_descriptors[dev]'
  ```

  This installs the app in editable mode, allowing you to make changes and see them reflected immediately without needing to reinstall.

- **For development using included arches-container configuration:**

  > arches-containers is a tool developed by Historic England to enable the quick set up of development environments.  You can find out more about arches-containers and how to install and use it, please see the [arches-containers documentation on PyPI](https://pypi.org/project/arches-containers/)

  Please ensure that you clone the arches-he-descriptors repository into a directory that uses underscores instead of hyphens, as the arches-containers configuration expects this format. For example, clone it to `arches_he_descriptors`.

    ```bash
    git clone https://github.com/HistoricEngland/arches-he-descriptors.git arches_he_descriptors
    ```

  This repository includes an `arches-containers` project configuration, so you can import, activate, and start the system as follows:

  1. Ensure Docker is installed and running.
  2. Navigate to your workspace directory (the root where your projects and containers live).
  3. Import the arches-container project configuration:

     ```bash
     act import -p arches_he_descriptors
     ```

  4. Activate the project:

     ```bash
     act activate -p arches_he_descriptors
     ```

  5. Start the system:

     ```bash
     act up
     ```

  6. Once setup and webpack builds are complete, open a browser and navigate to `http://localhost:8002` or use `act view` in a terminal to open the project in your default browser.

## Using This App in Your Arches Project

While you can use Arches HE Descriptors as a standalone app, you may wish to use it as part of an Arches Project.  The following steps explain how to do this:

### 1. Add to `your_project/pyproject.toml`

  Add the following to your `pyproject.toml` dependencies (in the `[project]` section):

  ```toml
  arches-he-descriptors @ git+https://github.com/HistoricEngland/arches-he-descriptors.git@release/1.0.x
  ```

  Example:

  ```toml
  dependencies = [
      "arches==7.6.17",
      "arches-he-descriptors @ git+https://github.com/HistoricEngland/arches-he-descriptors.git@release/1.0.x",
  ]
  ```

### 2. Update `your_project/your_project/settings.py`

Add to `INSTALLED_APPS` and `ARCHES_APPLICATIONS`:

```python
INSTALLED_APPS = (
    # Keep all existing installed applications.
    ...
    "your_project",
    "arches_he_descriptors",
)
ARCHES_APPLICATIONS = (
    # Keep all existing Arches applications.
    ...
    "arches_he_descriptors",
)
```

The ellipses represent your existing entries, not literal Python values to add.
Do not replace an existing `ARCHES_APPLICATIONS` list or tuple with only this app.

### 3. Run Database Migrations

Run the following command to apply any database migrations required by this app:

> if using the arches-containers, run this in the application container

```bash
python manage.py migrate
```

### 4. Register and Assign the Function

Migrations create the descriptor configuration table; they do not register the
Arches function. From your project's management-command directory, run:

```bash
python manage.py fn register --source /path/to/arches_he_descriptors/functions/arches_he_descriptors.py
python manage.py fn list
```

Replace the source path with the installed app's function file. In this project's
Docker container, the registration command is:

```bash
python manage.py fn register --source /web_root/arches_he_descriptors/arches_he_descriptors/functions/arches_he_descriptors.py
```

Confirm that `Arches HE Descriptors` appears in the list. In the Arches graph
designer, assign it to the target resource model as its primary descriptor
function, replacing the existing primary descriptor assignment. Keep exactly one
primary descriptor function assigned to that graph.

### 5. Configure Descriptor Rendering

Create a graph-specific
[`DisplayDescriptorGraphConfig`](arches_he_descriptors/models.py) record using
the Django admin's **Display descriptor graph configs** page. Select the target
graph and enter YAML describing its fields and ordered rendering rules.

For the supplied Monument graph, a name configuration is:

```yaml
fields:
  - name: Monument Name
    subfields:
      - name: Monument Name Use Type
        alias: NameUse
  - name: Primary Reference Number
display_descriptor_rules:
  - rule:
      - name: Monument Name
        field_filters:
          NameUse: "Primary|FIRST"
        operations:
          - first
      - name: Primary Reference Number
    format: "[{Primary Reference Number}] {Monument Name}"
```

Adapt field names to your graph. Each subfield must belong to the same nodegroup
as its parent field, and populated concept fields must reference valid concept
value UUIDs in the destination database.

For the function's **name** descriptor configuration, enable `show_prn=True`.
In the current implementation, this flag enables the YAML-backed name-rendering
path; the reference number is included by the YAML format, not automatically
prefixed by the flag. With `show_prn=False`, the function returns the existing
stored name instead. Missing configuration or an empty rendered result produces
`Undefined` when YAML-backed name rendering is enabled.

Publish the graph after configuring its function assignment. Existing resources
need descriptor regeneration to reflect configuration changes; saving the YAML
alone does not regenerate their stored names. The name integration tests verify
this through `Resource.save_descriptors(descriptors=("name",))`.

The description priority example `Summary|Full|FIRST` is currently verified
through the service with inline configuration; it is not a separate
description-specific function configuration demonstrated by these tests.

### 6. Install and Build Front-End Dependencies

From the directory containing your `your_project/package.json`:

> if using arches-containers, run this in the application container or restart the webpack

```bash
npm install
npm run build_development
```

### 7. Start Your Arches Project

```bash
python manage.py runserver
```

## License

This project is licensed under the GNU AGPLv3. See the LICENSE file for details.

---

For more information on deploying your Arches project, see the [Arches Deployment Guide](https://arches.readthedocs.io/en/stable/deployment/).
