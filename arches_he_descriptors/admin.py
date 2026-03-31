from django import forms
from django.contrib import admin
from arches.app.models.models import GraphModel

from .models import DisplayDescriptorGraphConfig


class DisplayDescriptorGraphConfigAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["yaml_config"].label = "YAML config"
        graph_choices = [
            (
                str(graph.graphid),
                f"{graph.name} ({graph.graphid})" if graph.name else str(
                    graph.graphid),
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
