from django.db import models


class DisplayDescriptorGraphConfig(models.Model):
    """Graph-scoped display descriptor YAML configuration."""

    graph_id = models.UUIDField(unique=True, db_index=True)
    yaml_config = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        from arches.app.models.models import GraphModel

        graph = GraphModel.objects.filter(graphid=self.graph_id).only("name").first()
        if graph and graph.name:
            return f"Display Descriptor Config for {graph.name}"

        return f"Display Descriptor Config for {self.graph_id}"

    class Meta:
        db_table = "display_descriptor_graph_config"
        verbose_name = "Display descriptor graph config"
        verbose_name_plural = "Display descriptor graph configs"
