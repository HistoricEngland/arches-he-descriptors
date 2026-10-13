from copy import deepcopy


SOURCE_DESCRIPTOR_FUNCTION_ID = "60000000-0000-0000-0000-000000000002"
EXCLUDED_FUNCTION_IDS = {
    "0434df8d-b98a-4b41-9a0a-68cd9214ad73",
    "184332d6-687d-4bcb-ae41-9aeb467fbdad",
    "d9a01773-6092-4cad-b331-ae725ae8fa88",
}
EXCLUDED_NODEGROUP_ID = "87d39b2b-f44f-11eb-af5e-a87eeabdefba"


def prepare_descriptor_graph(source, descriptor_details):
    graph = deepcopy(source)
    graph["template_id"] = "50000000-0000-0000-0000-000000000001"
    graph["config"] = {}

    for fields, records in (
        (("name", "description", "subtitle"), [graph]),
        (
            ("name", "description", "instructions", "helptitle", "helptext"),
            graph["cards"],
        ),
        (("label",), graph["cards_x_nodes_x_widgets"]),
    ):
        for record in records:
            for field in fields:
                if isinstance(record.get(field), str):
                    record[field] = {"en": record[field]}

    if any(
        group["parentnodegroup_id"] == EXCLUDED_NODEGROUP_ID
        for group in graph["nodegroups"]
    ):
        raise ValueError("The excluded BNG nodegroup unexpectedly has child nodegroups")

    excluded_nodes = {
        node["nodeid"]
        for node in graph["nodes"]
        if node["nodegroup_id"] == EXCLUDED_NODEGROUP_ID
    }
    graph["nodes"] = [
        node for node in graph["nodes"] if node["nodeid"] not in excluded_nodes
    ]
    graph["edges"] = [
        edge
        for edge in graph["edges"]
        if edge["domainnode_id"] not in excluded_nodes
        and edge["rangenode_id"] not in excluded_nodes
    ]
    graph["nodegroups"] = [
        group
        for group in graph["nodegroups"]
        if group["nodegroupid"] != EXCLUDED_NODEGROUP_ID
    ]
    graph["cards"] = [
        card for card in graph["cards"] if card["nodegroup_id"] != EXCLUDED_NODEGROUP_ID
    ]
    graph["cards_x_nodes_x_widgets"] = [
        widget
        for widget in graph["cards_x_nodes_x_widgets"]
        if widget["node_id"] not in excluded_nodes
    ]

    assignments = graph["functions_x_graphs"]
    unexpected_functions = (
        {assignment["function_id"] for assignment in assignments}
        - EXCLUDED_FUNCTION_IDS
        - {SOURCE_DESCRIPTOR_FUNCTION_ID}
    )
    if unexpected_functions:
        raise ValueError(
            f"Unexpected source graph functions: {sorted(unexpected_functions)}"
        )
    descriptor_assignments = [
        assignment
        for assignment in assignments
        if assignment["function_id"] == SOURCE_DESCRIPTOR_FUNCTION_ID
    ]
    if len(descriptor_assignments) != 1:
        raise ValueError("The source graph must have exactly one descriptor assignment")

    assignment = descriptor_assignments[0]
    assignment["function_id"] = descriptor_details["functionid"]
    config = assignment["config"]
    defaults = descriptor_details["defaultconfig"]
    for key, value in defaults.items():
        config.setdefault(key, deepcopy(value))
    config["module"] = defaults["module"]
    config["class_name"] = defaults["class_name"]
    for descriptor, descriptor_defaults in defaults["descriptor_types"].items():
        descriptor_config = config["descriptor_types"].setdefault(descriptor, {})
        for key, value in descriptor_defaults.items():
            descriptor_config.setdefault(key, deepcopy(value))
    config["descriptor_types"]["name"]["show_prn"] = True
    graph["functions_x_graphs"] = descriptor_assignments
    return graph
