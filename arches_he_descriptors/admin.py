from django import forms
from django.contrib import admin
import json
import yaml
from arches.app.models.models import GraphModel

from .models import DisplayDescriptorGraphConfig
from .display_descriptor.yaml_transform import (
    normalize_config_yaml_for_graph,
    extract_yaml_section,
    _load_json_sections,
    DESCRIPTOR_TYPES,
)

_SECTION_LABELS = {
    "display_name": "Display name YAML",
    "display_description": "Display description YAML",
    "map_popup": "Map popup YAML",
}

_YAML_TEXTAREA = forms.Textarea(
    attrs={
        "rows": 28,
        "cols": 120,
        "style": "font-family: monospace; white-space: pre; tab-size: 2;",
        "spellcheck": "false",
    }
)


class DisplayDescriptorGraphConfigAdminForm(forms.ModelForm):
    yaml_config_display_name = forms.CharField(
        widget=_YAML_TEXTAREA,
        required=False,
        label=_SECTION_LABELS["display_name"],
    )
    yaml_config_display_description = forms.CharField(
        widget=_YAML_TEXTAREA,
        required=False,
        label=_SECTION_LABELS["display_description"],
    )
    yaml_config_map_popup = forms.CharField(
        widget=_YAML_TEXTAREA,
        required=False,
        label=_SECTION_LABELS["map_popup"],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        graph_choices = [
            (
                str(graph.graphid),
                f"{graph.name} ({graph.graphid})" if graph.name else str(graph.graphid),
            )
            for graph in GraphModel.objects.filter(
                isresource=True,
                ontology_id__isnull=False,
            )
            .order_by("name")
            .only("graphid", "name")
        ]
        self.fields["graph_id"] = forms.ChoiceField(
            choices=graph_choices,
            label="Graph id",
            required=True,
            help_text="Select a graph by name; the graph UUID is stored.",
        )

        if self.instance and self.instance.pk and self.instance.graph_id:
            self.initial["graph_id"] = str(self.instance.graph_id)

        # Populate per-section fields from the stored yaml_config
        if self.instance and self.instance.pk and self.instance.yaml_config:
            for dt in DESCRIPTOR_TYPES:
                section_yaml = extract_yaml_section(self.instance.yaml_config, dt)
                if section_yaml:
                    self.initial[f"yaml_config_{dt}"] = section_yaml

    def clean_graph_id(self):
        value = self.cleaned_data.get("graph_id")
        if not value:
            return value

        from uuid import UUID

        return UUID(str(value))

    def _get_graph_id_for_validation(self):
        """Return graph_id for validation from the first available source."""
        graph_id = self.cleaned_data.get("graph_id")
        if graph_id:
            return graph_id
        if self.instance and self.instance.graph_id:
            return self.instance.graph_id
        # Fall back to raw POST data before clean_graph_id has run
        raw = self.data.get("graph_id")
        if raw:
            from uuid import UUID
            try:
                return UUID(str(raw))
            except (ValueError, AttributeError):
                pass
        return None

    def _clean_yaml_section(self, field_name: str) -> str:
        section_yaml = self.cleaned_data.get(field_name, "").strip()
        if not section_yaml:
            return ""

        graph_id = self._get_graph_id_for_validation()
        if not graph_id:
            return section_yaml

        try:
            normalized = normalize_config_yaml_for_graph(section_yaml, graph_id)
        except ValueError as exc:
            raise forms.ValidationError(str(exc))
        except yaml.YAMLError as exc:
            raise forms.ValidationError(f"Invalid YAML in input: {str(exc)}")
        except Exception as exc:
            raise forms.ValidationError(
                f"Error processing input configuration: {str(exc)}"
            )

        try:
            yaml.safe_load(normalized)
        except yaml.YAMLError as exc:
            if "**" in normalized:
                if hasattr(self.data, "_mutable"):
                    self.data._mutable = True
                self.data[field_name] = normalized
                if hasattr(self.data, "_mutable"):
                    self.data._mutable = False
                raise forms.ValidationError(
                    "The configuration contains duplicate widget labels (marked with **). "
                    "This means multiple fields in the card widget configuration share the same label. "
                    "Please check your graph's card widget setup and use the graph UUID comments to "
                    "identify which fields to keep. Delete the duplicate field lines you don't need, "
                    "then remove the ** markers."
                )
            else:
                raise forms.ValidationError(
                    f"Invalid YAML after normalization: {str(exc)}"
                )
        except Exception as exc:
            if hasattr(self.data, "_mutable"):
                self.data._mutable = True
            self.data[field_name] = normalized
            if hasattr(self.data, "_mutable"):
                self.data._mutable = False
            raise forms.ValidationError(f"Invalid YAML configuration: {str(exc)}")

        return normalized

    def clean_yaml_config_display_name(self):
        return self._clean_yaml_section("yaml_config_display_name")

    def clean_yaml_config_display_description(self):
        return self._clean_yaml_section("yaml_config_display_description")

    def clean_yaml_config_map_popup(self):
        return self._clean_yaml_section("yaml_config_map_popup")

    def clean(self):
        cleaned_data = super().clean()
        existing_yaml = self.instance.yaml_config if self.instance and self.instance.pk else None

        # Load existing sections without round-tripping to preserve formatting
        sections: dict = {}
        if existing_yaml:
            existing = _load_json_sections(existing_yaml)
            if existing is not None:
                sections = existing
            else:
                # Migrate legacy YAML format on first save
                try:
                    data = yaml.safe_load(existing_yaml)
                    if isinstance(data, dict):
                        if "fields" in data:
                            sections["display_name"] = existing_yaml
                        else:
                            for dt in DESCRIPTOR_TYPES:
                                if dt in data:
                                    sections[dt] = yaml.safe_dump(data[dt], sort_keys=False)
                except yaml.YAMLError:
                    pass

        for dt in DESCRIPTOR_TYPES:
            section_yaml = cleaned_data.get(f"yaml_config_{dt}", "").strip()
            if section_yaml:
                sections[dt] = section_yaml  # store the raw string — no round-trip
            else:
                sections.pop(dt, None)

        self._merged_yaml = json.dumps(sections) if sections else ""
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.yaml_config = self._merged_yaml
        if commit:
            instance.save()
        return instance

    class Meta:
        model = DisplayDescriptorGraphConfig
        exclude = ("yaml_config",)


@admin.register(DisplayDescriptorGraphConfig)
class DisplayDescriptorGraphConfigAdmin(admin.ModelAdmin):
    form = DisplayDescriptorGraphConfigAdminForm
    change_form_template = (
        "admin/arches_he_descriptors/displaydescriptorgraphconfig/change_form.html"
    )
    list_display = ("graph_id", "graph_name", "updated_at", "created_at")
    search_fields = ("graph_id",)
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "graph_id",
        "yaml_config_display_name",
        "yaml_config_display_description",
        "yaml_config_map_popup",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):
        from django.db.models import OuterRef, Subquery

        queryset = super().get_queryset(request)
        graph_names = GraphModel.objects.filter(graphid=OuterRef("graph_id")).values(
            "name"
        )
        queryset = queryset.annotate(
            graph_name_annotated=Subquery(graph_names[:1])
        ).order_by("graph_name_annotated")
        return queryset

    @admin.display(description="Graph name", ordering="graph_name_annotated")
    def graph_name(self, obj):
        return obj.graph_name_annotated or "-"

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        if not search_term:
            return queryset, use_distinct

        graph_ids = GraphModel.objects.filter(name__icontains=search_term).values_list(
            "graphid", flat=True
        )
        graph_config_queryset = self.get_queryset(request).filter(
            graph_id__in=graph_ids
        )
        queryset |= graph_config_queryset
        return queryset, use_distinct

