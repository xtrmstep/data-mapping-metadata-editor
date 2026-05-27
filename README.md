# Data Mapping Metadata Editor

A lightweight local tool for preparing mappings between source data and lakehouse tables.

It is designed for data engineers who need to:

- import source and destination information
- upload schema descriptions
- define field-level mappings
- export completed mappings

The typical flow is simple: create a source and destination pair, add schemas for both sides, configure how each destination field should be populated, and export the finished mapping.

The tool is intended for local use and keeps the workflow focused on mapping authoring rather than platform administration.
