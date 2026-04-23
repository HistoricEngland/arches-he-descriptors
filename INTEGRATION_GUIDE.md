# Implementing Arches HE Descriptor into an Existing Arches Application

## .arches_containers/mariner-proj/docker-compose.yml

Added:

 ``` yaml
 ../../arches_he_descriptors:/web_root/arches_he_descriptors
 ```
 
to the `volumes` section of the following services:

``` yaml
- marinerproj
- marinerproj-livereload
- marinerproj-webpack
```

## .arches_containers/mariner_proj/Dockerfile

Added:

``` dockerfile
ARG ARCHES_HE_DESCRIPTORS_PATH=./arches_he_descriptors
```

``` dockerfile
# Install the arches_he_descriptors package in editable mode
ENV ARCHES_HE_DESCRIPTORS=${WEB_ROOT}/arches_he_descriptors
COPY $ARCHES_HE_DESCRIPTORS_PATH ${ARCHES_HE_DESCRIPTORS}
WORKDIR ${ARCHES_HE_DESCRIPTORS}
RUN pip install -e '.[dev]'
```

## /mariner/arches_he_descriptors/pyproject.toml

Update the `dependencies` to:

``` toml
dependencies = [
     "arches>=7.6.23,<7.7.0",
    "PyYAML>=6.0",
]
```

to the following:

``` toml
dependencies = [
    "arches>=7.6.17,<7.7.0",
    "PyYAML>=6.0",
]
```

This is necessary because `config.json` sets `arches_repo_branch` to `stable/7.6.17`, while the original dependency required `>=7.6.23`.


## /mariner/mariner_proj/mariner_proj/urls.py

Add:

``` python
path("", include("arches_he_descriptors.urls")),
```
Because the descriptor application uses API endpoints, it was necessary to move:

``` python
path("", include("mariner_app.urls")),
```

to the end of the include list, because API calls were being caught by the catch-all behavior in `mariner_app.urls`, which broke async API calls from the Django admin backend.


## /mariner/mariner_proj/mariner_proj/settings.py

Added:

``` python
DATATYPE_LOCATIONS.append("arches_he_descriptors.datatypes")
FUNCTION_LOCATIONS.append("arches_he_descriptors.functions")
SEARCH_COMPONENT_LOCATIONS.append("arches_he_descriptors.search.components")
```

``` python
INSTALLED_APPS = (
    ...
    "arches_he_descriptors",
)
```

``` python
ARCHES_APPLICATIONS = ("mariner_app", "arches_he_sysref_funcs", "arches_he_descriptors")
```

Finally, spin up the project and apply database migrations:

``` shell
python manage.py migrate
```

Finally, register the Arches HE Descriptor function:

``` shell
python manage.py fn register --source /web_root/arches_he_descriptors/arches_he_descriptors/functions/arches_he_descriptors.py
```