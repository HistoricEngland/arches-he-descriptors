from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path
from arches_he_descriptors.display_descriptor.views import (
    get_display_descriptor,
    get_display_descriptor_graph_config,
    preview_display_descriptor,
    test_config_for_resource,
)

urlpatterns = [
    # project-level urls
    path(
        "api/display-descriptor/<uuid:resource_id>/",
        get_display_descriptor,
        name="get_display_descriptor",
    ),
    path(
        "api/display-descriptor/config/<uuid:graph_id>/",
        get_display_descriptor_graph_config,
        name="get_display_descriptor_graph_config",
    ),
    path(
        "api/display-descriptor/preview/",
        preview_display_descriptor,
        name="preview_display_descriptor",
    ),
    path(
        "api/display-descriptor/admin-test/",
        test_config_for_resource,
        name="test_config_for_resource",
    ),
]

# Ensure Arches core urls are superseded by project-level urls
urlpatterns.append(path("", include("arches.urls")))

# Adds URL pattern to serve media files during development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Only handle i18n routing in active project. This will still handle the routes provided by Arches core and Arches applications,
# but handling i18n routes in multiple places causes application errors.
if settings.ROOT_URLCONF == __name__:
    if settings.SHOW_LANGUAGE_SWITCH is True:
        urlpatterns = i18n_patterns(*urlpatterns)

    urlpatterns.append(path("i18n/", include("django.conf.urls.i18n")))
