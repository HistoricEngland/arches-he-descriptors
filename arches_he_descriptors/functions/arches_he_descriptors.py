import logging
from arches.app.functions.primary_descriptors import AbstractPrimaryDescriptorsFunction
from django.utils.translation import gettext as _
from arches_he_descriptors.display_descriptor.service import (
    render_display_descriptor_for_resource,
)

logger = logging.getLogger(__name__)

details = {
    "functionid": "60000000-0000-0000-0000-000000000003",
    "name": "Arches HE Descriptors",
    "type": "primarydescriptors",
    "modulename": "arches_he_descriptors.py",
    "description": "Function that provides the primary descriptors for HE resources",
    "defaultconfig": {
        "module": "arches_he_descriptors.functions.arches_he_descriptors",
        "class_name": "ArchesHEDescriptors",
        "descriptor_types": {
            "name": {
                "nodegroup_id": "",
                "string_template": "",
                "show_prn": False,
            },
            "description": {
                "nodegroup_id": "",
                "string_template": "",
            },
            "map_popup": {
                "nodegroup_id": "",
                "string_template": "",
            },
        },
        "triggering_nodegroups": [],
    },
    "classname": "ArchesHEDescriptors",
    "component": "views/components/functions/arches-he-descriptors",
}


class ArchesHEDescriptors(AbstractPrimaryDescriptorsFunction):
    def get_primary_descriptor_from_nodes(self, resource, config, context=None, descriptor=None):
        language = "en"
        if isinstance(context, dict) and context.get("language"):
            language = context["language"]

        if config.get("show_prn") is False:
            try:
                return resource.descriptors[language][descriptor]
            except KeyError:
                return None

        try:
            descriptor_value = render_display_descriptor_for_resource(
                resource_id=str(resource.resourceinstanceid),
                language=language,
                strict_sortorder=False,
            )
        except ValueError as exc:
            logger.warning(
                _("Unable to render display descriptor for resource {0}: {1}").format(
                    resource.resourceinstanceid, exc
                )
            )
            return _("Undefined")
        except Exception:
            logger.exception(
                _("Unexpected error rendering display descriptor for resource {0}").format(
                    resource.resourceinstanceid
                )
            )
            return _("Undefined")

        if descriptor_value is None or str(descriptor_value).strip() == "":
            return _("Undefined")

        return str(descriptor_value)
