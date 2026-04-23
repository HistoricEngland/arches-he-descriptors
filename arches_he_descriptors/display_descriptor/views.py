from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.conf import settings
from ..models import DisplayDescriptorGraphConfig
from ..display_descriptor.service import (
    render_display_descriptor,
    render_display_descriptor_for_resource,
    DisplayDescriptorService,
)
import json
import yaml
from time import perf_counter


def get_display_descriptor_graph_config(request, graph_id):
    """Return graph-scoped YAML descriptor configuration for the function editor."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    row = (
        DisplayDescriptorGraphConfig.objects.filter(graph_id=graph_id)
        .values("yaml_config")
        .first()
    )

    yaml_config = row.get("yaml_config") if row else None
    configured = isinstance(yaml_config, str) and yaml_config.strip() != ""

    return JsonResponse(
        {
            "graph_id": str(graph_id),
            "configured": configured,
            "yaml_config": yaml_config if configured else None,
        }
    )


def _is_descriptor_only(value):
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no", "n", "off"}


def _is_truthy(value):
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _execute_with_sql_capture(func, include_sql=False):
    if not include_sql:
        return func(), []

    sql_queries = []

    def _wrapper(execute, sql, params, many, context):
        start = perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            sql_queries.append(
                {
                    "sql": sql,
                    "params": repr(params) if params is not None else None,
                    "many": many,
                    "duration_ms": round((perf_counter() - start) * 1000, 3),
                }
            )

    with connection.execute_wrapper(_wrapper):
        result = func()

    return result, sql_queries


def _validate_sql_toggle(include_sql):
    if include_sql and not getattr(settings, "DEBUG", False):
        raise ValueError("include_sql is only available when DEBUG=True")


def _add_sql_metadata(payload, include_sql, sql_queries, request_start):
    if include_sql:
        payload["execution_time_ms"] = round(
            (perf_counter() - request_start) * 1000, 3)
        payload["sql_query_count"] = len(sql_queries)
        payload["sql_queries"] = sql_queries
    return payload


def _add_yaml_metadata(payload, include_yaml, yaml_config, source=None):
    if include_yaml:
        payload["yaml_config"] = yaml_config
        payload["yaml_config_source"] = source
    return payload


def _serialize_config_to_yaml(config_data):
    if config_data is None:
        return None
    return yaml.safe_dump(config_data, sort_keys=False)


def _get_graph_yaml_for_resource(resource_id):
    from arches.app.models.models import ResourceInstance

    resource = (
        ResourceInstance.objects.filter(resourceinstanceid=resource_id)
        .values("graph_id")
        .first()
    )
    if not resource:
        raise ValueError(f"Resource instance not found: {resource_id}")

    row = (
        DisplayDescriptorGraphConfig.objects.filter(graph_id=resource["graph_id"])
        .values("yaml_config")
        .first()
    )
    yaml_config = row.get("yaml_config") if row else None
    return yaml_config if isinstance(yaml_config, str) and yaml_config.strip() else None


@csrf_exempt
def get_display_descriptor(request, resource_id):
    """
    API endpoint to get display descriptor for a resource.

    Usage: GET /api/display-descriptor/<resource_id>/
    Usage: POST /api/display-descriptor/<resource_id>/
    Body: {"config": {...}}  (config is optional)

    Optional query params:
    - descriptor_only=false|0|no|off : include input payload in response (POST only)
    - include_sql=true|1|yes|on : include captured SQL statements and timings
    - include_yaml=true|1|yes|on : include resolved YAML config string in response
    - strict_sortorder=true|1|yes|on : fail if mixed null/non-null sortorder exists in a nodegroup
    """
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        request_start = perf_counter()
        include_sql = _is_truthy(request.GET.get("include_sql"))
        include_yaml = _is_truthy(request.GET.get("include_yaml"))
        strict_sortorder = _is_truthy(request.GET.get("strict_sortorder"))
        _validate_sql_toggle(include_sql)

        if request.method == "GET":
            descriptor, sql_queries = _execute_with_sql_capture(
                lambda: render_display_descriptor_for_resource(
                    resource_id,
                    strict_sortorder=strict_sortorder,
                ),
                include_sql=include_sql,
            )
            payload = {"resource_id": resource_id,
                       "display_descriptor": descriptor}
            if include_yaml:
                payload = _add_yaml_metadata(
                    payload,
                    include_yaml=True,
                    yaml_config=_get_graph_yaml_for_resource(resource_id),
                    source="graph",
                )
            return JsonResponse(
                _add_sql_metadata(payload, include_sql,
                                  sql_queries, request_start)
            )

        data = json.loads(request.body) if request.body else {}
        config = data.get("config")
        descriptor_only = _is_descriptor_only(
            request.GET.get("descriptor_only"))
        yaml_config = None
        yaml_config_source = None
        if include_yaml:
            if config is not None:
                yaml_config = _serialize_config_to_yaml(config)
                yaml_config_source = "request"
            else:
                yaml_config = _get_graph_yaml_for_resource(resource_id)
                yaml_config_source = "graph"

        service = DisplayDescriptorService()
        resource_payload, sql_queries_data = _execute_with_sql_capture(
            lambda: service.get_resource_data(
                resource_id,
                strict_sortorder=strict_sortorder,
                config_data=config,
                return_config=True,
            ),
            include_sql=include_sql,
        )

        resource_data, resolved_config = resource_payload

        render_func = (
            (lambda: service.render_with_config(resource_data, config))
            if config is not None
            else (
                (lambda: None)
                if resolved_config is None
                else (
                    lambda: service.render_with_parsed_config(
                        resource_data,
                        resolved_config,
                    )
                )
            )
        )
        descriptor, sql_queries_render = _execute_with_sql_capture(
            render_func,
            include_sql=include_sql,
        )

        sql_queries = sql_queries_data + sql_queries_render

        if descriptor_only:
            payload = {"display_descriptor": descriptor}
            payload = _add_yaml_metadata(
                payload,
                include_yaml=include_yaml,
                yaml_config=yaml_config,
                source=yaml_config_source,
            )
            return JsonResponse(
                _add_sql_metadata(payload, include_sql,
                                  sql_queries, request_start)
            )

        payload = {
            "resource_id": resource_id,
            "input": resource_data,
            "display_descriptor": descriptor,
        }
        payload = _add_yaml_metadata(
            payload,
            include_yaml=include_yaml,
            yaml_config=yaml_config,
            source=yaml_config_source,
        )
        return JsonResponse(
            _add_sql_metadata(payload, include_sql, sql_queries, request_start)
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def preview_display_descriptor(request):
    """
    API endpoint to preview display descriptor for test data.

    Usage: POST /api/display-descriptor/preview/
    Body: {"resource": {...}, "config": {...}}  (config is optional)

    If config is provided, it will be used for rendering instead of the default config.
    Config can be a dict with keys: "fields" and "display_descriptor_rules"

    Optional query param:
    - descriptor_only=false|0|no|off : returns {"input": {...}, "display_descriptor": "..."}
    - default behavior (or descriptor_only=true) returns only {"display_descriptor": "..."}
    - include_sql=true|1|yes|on : include captured SQL statements and timings
    - strict_sortorder=true|1|yes|on : accepted for API consistency (no effect in preview mode)
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        request_start = perf_counter()
        data = json.loads(request.body)
        resource = data.get("resource", {})
        config = data.get("config")
        descriptor_only = _is_descriptor_only(
            request.GET.get("descriptor_only"))
        include_sql = _is_truthy(request.GET.get("include_sql"))
        strict_sortorder = _is_truthy(request.GET.get("strict_sortorder"))
        _validate_sql_toggle(include_sql)

        if strict_sortorder:
            # Preview mode renders in-memory resource payloads and does not load tiles.
            # The parameter is accepted for consistency with DB-backed endpoints.
            pass

        # Use provided config when present; otherwise no-op (no default file fallback).
        if config is not None:
            try:
                service = DisplayDescriptorService()
                descriptor, sql_queries = _execute_with_sql_capture(
                    lambda: service.render_with_config(resource, config),
                    include_sql=include_sql,
                )
            except ValueError as e:
                return JsonResponse({"error": f"Invalid config: {str(e)}"}, status=400)
        else:
            descriptor, sql_queries = _execute_with_sql_capture(
                lambda: render_display_descriptor(resource),
                include_sql=include_sql,
            )

        if descriptor_only:
            payload = {"display_descriptor": descriptor}
            return JsonResponse(
                _add_sql_metadata(payload, include_sql,
                                  sql_queries, request_start)
            )

        payload = {"input": resource, "display_descriptor": descriptor}
        return JsonResponse(
            _add_sql_metadata(payload, include_sql, sql_queries, request_start)
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def test_config_for_resource(request):
    """
    Admin test endpoint to render display descriptor.

    Usage: POST /api/display-descriptor/admin-test/
    Body: {"resource_id": "<uuid>", "graph_id": "<uuid>", "yaml_config": "..."}

    Returns: {"display_descriptor": "...", "error": "..."} or error response
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body) if request.body else {}
        resource_id = data.get("resource_id")
        graph_id = data.get("graph_id")
        yaml_config = data.get("yaml_config")

        if not resource_id:
            return JsonResponse({"error": "resource_id is required"}, status=400)
        if not graph_id:
            return JsonResponse({"error": "graph_id is required"}, status=400)

        # If yaml_config not provided in request, try to fetch from database
        if not yaml_config:
            from ..models import DisplayDescriptorGraphConfig

            config_row = (
                DisplayDescriptorGraphConfig.objects.filter(graph_id=graph_id)
                .values("yaml_config")
                .first()
            )

            if not config_row:
                return JsonResponse(
                    {
                        "display_descriptor": None,
                        "error": f"No display descriptor config found for graph {graph_id}",
                    }
                )

            yaml_config = config_row.get("yaml_config")

        if not yaml_config:
            return JsonResponse(
                {
                    "display_descriptor": None,
                    "error": "YAML config is empty",
                }
            )

        try:
            config_dict = yaml.safe_load(yaml_config)
        except yaml.YAMLError as e:
            return JsonResponse(
                {
                    "display_descriptor": None,
                    "error": f"Invalid YAML in config: {str(e)}",
                }
            )

        service = DisplayDescriptorService()

        descriptor = service.render_for_resource(
            resource_id=resource_id,
            config_data=config_dict,
        )

        return JsonResponse(
            {
                "display_descriptor": descriptor,
                "error": None,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except ValueError as e:
        return JsonResponse(
            {
                "display_descriptor": None,
                "error": str(e),
            }
        )
    except Exception as e:
        return JsonResponse(
            {
                "display_descriptor": None,
                "error": str(e),
            },
            status=500,
        )
