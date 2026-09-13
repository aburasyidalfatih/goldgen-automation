"""Shared Graph API version for publishing and read-only collectors."""
import os
import re

GRAPH_API_VERSION = os.getenv('META_GRAPH_API_VERSION', 'v26.0')
if not re.fullmatch(r'v\d+\.0', GRAPH_API_VERSION):
    raise ValueError('META_GRAPH_API_VERSION must look like v26.0')
GRAPH_API_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}'
