import re
from django_hosts import patterns, host

host_patterns = patterns(
    "",
    host(
        re.sub(r"_", r"-", r"arches_he_descriptors"),
        "arches_he_descriptors.urls",
        name="arches_he_descriptors",
    ),
)
