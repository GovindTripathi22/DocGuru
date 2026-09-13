from typing import Dict, List, Any

# Tool declarations formatted for Google GenAI / Gemma 4 function calling
GEMMA_DOCUMENT_TOOLS = [
    {
        "name": "get_template_spec",
        "description": "Inspect the complete locked template specification including available styles, layouts, fonts, and dimensions.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_available_styles",
        "description": "Get all pre-existing paragraph and heading styles available in the template.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_existing_layouts",
        "description": "Get all pre-existing slide layout names available in the presentation master.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "insert_heading",
        "description": "Insert a section heading into the document using an EXACT pre-existing heading style from the template.",
        "parameters": {
            "type": "object",
            "properties": {
                "style": {
                    "type": "string",
                    "description": "Must be an exact heading style name existing in the template (e.g. 'Heading 1', 'Heading 2', 'ChapterTitle')."
                },
                "content": {
                    "type": "string",
                    "description": "The text content of the heading."
                }
            },
            "required": ["style", "content"]
        }
    },
    {
        "name": "insert_paragraph",
        "description": "Insert a body paragraph into the document using an EXACT pre-existing style from the template.",
        "parameters": {
            "type": "object",
            "properties": {
                "style": {
                    "type": "string",
                    "description": "Must be an existing style from the template (e.g. 'Normal', 'Body Text')."
                },
                "content": {
                    "type": "string",
                    "description": "The paragraph text content."
                }
            },
            "required": ["style", "content"]
        }
    },
    {
        "name": "insert_bullet_item",
        "description": "Insert a bullet point into the document using the template's existing list bullet style.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The bullet point text."
                },
                "level": {
                    "type": "integer",
                    "description": "Indentation level (0 for top-level)."
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "insert_table",
        "description": "Insert a table by cloning the exact border, shading, and cell styling of an existing template table.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_table_index": {
                    "type": "integer",
                    "description": "Index of the template table whose borders and styling should be cloned (default 0)."
                },
                "headers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column header text items."
                },
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "description": "Table rows and cell contents."
                },
                "title": {
                    "type": "string",
                    "description": "Optional title for the table."
                }
            },
            "required": ["headers", "rows"]
        }
    },
    {
        "name": "insert_slide",
        "description": "Create a new slide by instantiating an EXACT existing slide layout from the master.",
        "parameters": {
            "type": "object",
            "properties": {
                "layout_name": {
                    "type": "string",
                    "description": "Exact layout name from the template (e.g. 'Title Slide', 'Title and Content', 'Two Content')."
                },
                "title": {
                    "type": "string",
                    "description": "Slide title text."
                },
                "subtitle": {
                    "type": "string",
                    "description": "Optional subtitle (for title layouts)."
                },
                "bullet_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Bullet points for the slide content placeholder."
                },
                "body_paragraphs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paragraph text for body placeholder."
                },
                "speaker_notes": {
                    "type": "string",
                    "description": "Optional speaker notes."
                }
            },
            "required": ["layout_name", "title"]
        }
    },
    {
        "name": "replace_text",
        "description": "Replace text in an existing document without modifying run formatting, colors, or fonts.",
        "parameters": {
            "type": "object",
            "properties": {
                "search_text": {
                    "type": "string",
                    "description": "Exact text string to find."
                },
                "replacement_text": {
                    "type": "string",
                    "description": "New text to substitute."
                }
            },
            "required": ["search_text", "replacement_text"]
        }
    }
]
