# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Sanitized `codex exec --json` streams captured from codex-cli 0.148.0.

Two runs, kept as the raw lines codex printed rather than as rebuilt dicts.
The item shapes here are the ones the parser has to survive, and one of them
cannot be spelled as a dict at all: a `web_search` item serializes `id` twice
-- the synthetic `item_N` the exec stream numbers its items with, then the
provider's own `exec-...` call id flattened over it -- so what the decoder
hands the parser is the provider id, and that is the identifier a web search
is correlated and recorded under.

Sanitized means the thread ids, the MCP server and tool names, the absolute
paths, and the long search / fetch payloads were replaced or shortened. Every
field name, item type, status value, and frame order is verbatim.
"""

TOOL_RUN_THREAD_ID = "01a0194a-30cb-7211-bbe6-853513634e0c"
FAILED_RUN_THREAD_ID = "01a0194b-9c3a-7f10-8bd4-2e7a11c05f93"
SEARCH_CALL_ID = "exec-2f1c8d0a-4b77-4c31-9d2e-6a5f0b8c1d34"
ABANDONED_SEARCH_CALL_ID = "exec-7b0c33d1-5a92-4e08-bf16-3c7d90e2a415"
SEARCH_QUERY = "codex exec json"
MCP_SERVER = "docsServer"
SEARCH_DOCS_TOOL = "search_docs"
FETCH_DOC_TOOL = "fetch_doc"
SEARCH_DOCS_NAME = f"{MCP_SERVER}.{SEARCH_DOCS_TOOL}"
FETCH_DOC_NAME = f"{MCP_SERVER}.{FETCH_DOC_TOOL}"
FETCHED_URL = "https://example.invalid/missing"
LIST_COMMAND = "/bin/bash -lc 'ls'"
# Spelled out again inside the raw line below, which cannot interpolate:
# the newline there has to reach the decoder as the two-character JSON
# escape rather than as an actual line break splitting the frame in two.
LIST_OUTPUT = "calc.py\n"
CHANGED_PATH = "calc.py"
TODO_TEXT = "Rename calc.py"
OPENING_MESSAGE = "Searching the web first."
CLOSING_MESSAGE = "Done."
REASONING_TEXT = "**Checking the docs tool**"
STREAM_ERROR_MESSAGE = "Model metadata for `example-model` not found."

MCP_ITEM_ID = "item_3"
COMMAND_ITEM_ID = "item_4"
FILE_CHANGE_ITEM_ID = "item_5"
TODO_ITEM_ID = "item_6"
FAILED_MCP_ITEM_ID = "item_0"

# Named apart from the run they belong to: a test that has to interleave a
# frame of its own around a search needs the captured lines themselves, not
# the whole stdout they sit in.
WEB_SEARCH_STARTED_LINE = (
    '{"type":"item.started","item":{"id":"item_1","type":"web_search",'
    f'"id":"{SEARCH_CALL_ID}","query":"",'
    '"action":{"type":"other"}}}'
)
WEB_SEARCH_COMPLETED_LINE = (
    '{"type":"item.completed","item":{"id":"item_1","type":"web_search",'
    f'"id":"{SEARCH_CALL_ID}","query":"{SEARCH_QUERY}",'
    f'"action":{{"type":"search","query":"{SEARCH_QUERY}"}}}}}}'
)

_TOOL_RUN_LINES = (
    f'{{"type":"thread.started","thread_id":"{TOOL_RUN_THREAD_ID}"}}',
    '{"type":"turn.started"}',
    (
        '{"type":"item.completed","item":{"id":"item_0",'
        f'"type":"agent_message","text":"{OPENING_MESSAGE}"}}}}'
    ),
    WEB_SEARCH_STARTED_LINE,
    WEB_SEARCH_COMPLETED_LINE,
    (
        '{"type":"item.completed","item":{"id":"item_2","type":"reasoning",'
        f'"text":"{REASONING_TEXT}"}}}}'
    ),
    (
        f'{{"type":"item.started","item":{{"id":"{MCP_ITEM_ID}",'
        f'"type":"mcp_tool_call","server":"{MCP_SERVER}",'
        f'"tool":"{SEARCH_DOCS_TOOL}",'
        f'"arguments":{{"query":"{SEARCH_QUERY}","limit":5}},'
        '"result":null,"error":null,"status":"in_progress"}}'
    ),
    (
        f'{{"type":"item.completed","item":{{"id":"{MCP_ITEM_ID}",'
        f'"type":"mcp_tool_call","server":"{MCP_SERVER}",'
        f'"tool":"{SEARCH_DOCS_TOOL}",'
        f'"arguments":{{"query":"{SEARCH_QUERY}","limit":5}},'
        r'"result":{"content":[{"type":"text","text":"{\"hits\":[]}"}],'
        '"structured_content":null},"error":null,"status":"completed"}}'
    ),
    (
        f'{{"type":"item.started","item":{{"id":"{COMMAND_ITEM_ID}",'
        f'"type":"command_execution","command":"{LIST_COMMAND}",'
        '"aggregated_output":"","exit_code":null,"status":"in_progress"}}'
    ),
    (
        f'{{"type":"item.completed","item":{{"id":"{COMMAND_ITEM_ID}",'
        f'"type":"command_execution","command":"{LIST_COMMAND}",'
        r'"aggregated_output":"calc.py\n","exit_code":0,'
        '"status":"completed"}}'
    ),
    (
        f'{{"type":"item.started","item":{{"id":"{FILE_CHANGE_ITEM_ID}",'
        f'"type":"file_change","changes":[{{"path":"{CHANGED_PATH}",'
        '"kind":"update"}],"status":"in_progress"}}'
    ),
    (
        f'{{"type":"item.completed","item":{{"id":"{FILE_CHANGE_ITEM_ID}",'
        f'"type":"file_change","changes":[{{"path":"{CHANGED_PATH}",'
        '"kind":"update"}],"status":"completed"}}'
    ),
    (
        f'{{"type":"item.started","item":{{"id":"{TODO_ITEM_ID}",'
        f'"type":"todo_list","items":[{{"text":"{TODO_TEXT}",'
        '"completed":false}]}}'
    ),
    (
        f'{{"type":"item.updated","item":{{"id":"{TODO_ITEM_ID}",'
        f'"type":"todo_list","items":[{{"text":"{TODO_TEXT}",'
        '"completed":false}]}}'
    ),
    (
        f'{{"type":"item.completed","item":{{"id":"{TODO_ITEM_ID}",'
        f'"type":"todo_list","items":[{{"text":"{TODO_TEXT}",'
        '"completed":true}]}}'
    ),
    (
        '{"type":"item.completed","item":{"id":"item_7",'
        f'"type":"agent_message","text":"{CLOSING_MESSAGE}"}}}}'
    ),
    (
        '{"type":"turn.completed","usage":{"input_tokens":106121,'
        '"cached_input_tokens":94464,"cache_write_input_tokens":0,'
        '"output_tokens":634,"reasoning_output_tokens":16}}'
    ),
)

_FAILED_RUN_LINES = (
    f'{{"type":"thread.started","thread_id":"{FAILED_RUN_THREAD_ID}"}}',
    '{"type":"turn.started"}',
    (
        f'{{"type":"item.started","item":{{"id":"{FAILED_MCP_ITEM_ID}",'
        f'"type":"mcp_tool_call","server":"{MCP_SERVER}",'
        f'"tool":"{FETCH_DOC_TOOL}","arguments":{{"url":"{FETCHED_URL}"}},'
        '"result":null,"error":null,"status":"in_progress"}}'
    ),
    (
        f'{{"type":"item.completed","item":{{"id":"{FAILED_MCP_ITEM_ID}",'
        f'"type":"mcp_tool_call","server":"{MCP_SERVER}",'
        f'"tool":"{FETCH_DOC_TOOL}","arguments":{{"url":"{FETCHED_URL}"}},'
        '"result":{"content":[{"type":"text","text":'
        f'"Failed to fetch {FETCHED_URL}: 404 Not Found"}}],'
        '"structured_content":null},"error":null,"status":"failed"}}'
    ),
    (
        '{"type":"item.started","item":{"id":"item_1","type":"web_search",'
        f'"id":"{ABANDONED_SEARCH_CALL_ID}","query":"",'
        '"action":{"type":"other"}}}'
    ),
    (
        '{"type":"item.completed","item":{"id":"item_2","type":"error",'
        f'"message":"{STREAM_ERROR_MESSAGE}"}}}}'
    ),
    (
        '{"type":"turn.failed","error":{"message":'
        '"stream disconnected before completion"}}'
    ),
)

TOOL_RUN_STDOUT = "\n".join(_TOOL_RUN_LINES)
FAILED_RUN_STDOUT = "\n".join(_FAILED_RUN_LINES)
