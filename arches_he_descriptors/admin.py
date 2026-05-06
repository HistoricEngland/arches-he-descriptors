from django import forms
from django.contrib import admin
from arches.app.models.models import GraphModel

from .models import DisplayDescriptorGraphConfig
from .display_descriptor.yaml_transform import normalize_config_yaml_for_graph


class DisplayDescriptorGraphConfigAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["yaml_config"].label = "YAML config"
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

    def clean_graph_id(self):
        value = self.cleaned_data.get("graph_id")
        if not value:
            return value

        from uuid import UUID

        return UUID(str(value))

    def clean_yaml_config(self):
        yaml_config = self.cleaned_data.get("yaml_config")
        graph_id = self.cleaned_data.get("graph_id")

        if not yaml_config:
            return yaml_config

        if not graph_id and self.instance and self.instance.graph_id:
            graph_id = self.instance.graph_id

        if not graph_id:
            return yaml_config

        import yaml

        try:
            normalized = normalize_config_yaml_for_graph(yaml_config, graph_id)
        except ValueError as exc:
            raise forms.ValidationError(str(exc))
        except yaml.YAMLError as exc:
            raise forms.ValidationError(f"Invalid YAML in input: {str(exc)}")
        except Exception as exc:
            raise forms.ValidationError(
                f"Error processing input configuration: {str(exc)}"
            )

        # Try to parse the normalized YAML to validate it
        try:
            yaml.safe_load(normalized)
        except yaml.YAMLError as exc:
            # Check if this is an intentional ambiguity block error
            if "**" in normalized:
                # Update the form's data to display the transformed YAML with ** markers
                if hasattr(self.data, "_mutable"):
                    self.data._mutable = True
                self.data["yaml_config"] = normalized
                if hasattr(self.data, "_mutable"):
                    self.data._mutable = False

                error_msg = (
                    "The configuration contains duplicate widget labels (marked with **). "
                    "This means multiple fields in the card widget configuration share the same label. "
                    "Please check your graph's card widget setup and use the graph UUID comments to identify which fields to keep. "
                    "Delete the duplicate field lines you don't need, then remove the ** markers."
                )
                raise forms.ValidationError(error_msg)
            else:
                raise forms.ValidationError(
                    f"Invalid YAML after normalization: {str(exc)}"
                )
        except Exception as exc:
            # Catch-all for any other parsing or validation errors
            if hasattr(self.data, "_mutable"):
                self.data._mutable = True
            self.data["yaml_config"] = normalized
            if hasattr(self.data, "_mutable"):
                self.data._mutable = False

            raise forms.ValidationError(f"Invalid YAML configuration: {str(exc)}")

        return normalized

    class Meta:
        model = DisplayDescriptorGraphConfig
        fields = "__all__"
        widgets = {
            "yaml_config": forms.Textarea(
                attrs={
                    "rows": 28,
                    "cols": 120,
                    "style": "font-family: monospace; white-space: pre; tab-size: 2;",
                    "spellcheck": "false",
                }
            )
        }


@admin.register(DisplayDescriptorGraphConfig)
class DisplayDescriptorGraphConfigAdmin(admin.ModelAdmin):
    form = DisplayDescriptorGraphConfigAdminForm
    change_form_template = (
        "admin/arches_he_descriptors/displaydescriptorgraphconfig/change_form.html"
    )
    list_display = ("graph_id", "graph_name", "updated_at", "created_at")
    search_fields = ("graph_id",)
    readonly_fields = ("created_at", "updated_at")
    fields = ("graph_id", "yaml_config", "created_at", "updated_at")

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
