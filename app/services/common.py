"""Source-type configuration shared between services and pages."""

SOURCE_TYPE_OPTIONS: dict[str, dict] = {
    "PostgreSQL sources": {
        "source_type": "postgres",
        "columns": [
            {"name": "source_type", "description": "Source type. For this import, value should identify PostgreSQL."},
            {"name": "cluster_name", "description": "Point of presence or datacenter name where the database server is located."},
            {"name": "source_server", "description": "PostgreSQL server name or identifier."},
            {"name": "source_database", "description": "Source PostgreSQL database name."},
            {"name": "source_schema", "description": "Source PostgreSQL schema name."},
            {"name": "source_table", "description": "Source PostgreSQL table name."},
            {"name": "destination_server", "description": "Destination server name or identifier."},
            {"name": "destination_database", "description": "Destination database name."},
            {"name": "destination_table", "description": "Destination table name."},
        ],
        "note": "PostgreSQL object names must not contain dots. Use underscores if separation is needed.",
    },
    "Kafka sources": {
        "source_type": "kafka",
        "columns": [
            {"name": "source_type", "description": "Source type. For this import, value should identify Kafka."},
            {"name": "cluster_name", "description": "Kafka cluster name or identifier."},
            {"name": "source_kafka", "description": "Kafka service or platform name."},
            {"name": "source_kafka_brokers", "description": "Kafka broker list."},
            {"name": "source_kafka_topic", "description": "Kafka topic name."},
            {"name": "destination_server", "description": "Destination server name or identifier."},
            {"name": "destination_database", "description": "Destination database name."},
            {"name": "destination_table", "description": "Destination table name."},
        ],
        "note": "Kafka topic names may contain dots, hyphens, and underscores. Destination object names must not contain dots; use underscores if separation is needed.",
    },
}
