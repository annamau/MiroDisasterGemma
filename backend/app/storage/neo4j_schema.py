"""
Neo4j Schema — Cypher queries for index creation and schema management.

Called by Neo4jStorage.create_graph() to set up vector + fulltext indexes.
"""

# Constraints
CREATE_GRAPH_UUID_CONSTRAINT = """
CREATE CONSTRAINT graph_uuid IF NOT EXISTS
FOR (g:Graph) REQUIRE g.graph_id IS UNIQUE
"""

CREATE_ENTITY_UUID_CONSTRAINT = """
CREATE CONSTRAINT entity_uuid IF NOT EXISTS
FOR (n:Entity) REQUIRE n.uuid IS UNIQUE
"""

CREATE_EPISODE_UUID_CONSTRAINT = """
CREATE CONSTRAINT episode_uuid IF NOT EXISTS
FOR (ep:Episode) REQUIRE ep.uuid IS UNIQUE
"""

# Vector indexes (Neo4j 5.11+)
CREATE_ENTITY_VECTOR_INDEX = """
CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
FOR (n:Entity) ON (n.embedding)
OPTIONS {indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
}}
"""

CREATE_RELATION_VECTOR_INDEX = """
CREATE VECTOR INDEX fact_embedding IF NOT EXISTS
FOR ()-[r:RELATION]-() ON (r.fact_embedding)
OPTIONS {indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
}}
"""

# Fulltext indexes (for BM25 keyword search)
CREATE_ENTITY_FULLTEXT_INDEX = """
CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
FOR (n:Entity) ON EACH [n.name, n.summary]
"""

CREATE_FACT_FULLTEXT_INDEX = """
CREATE FULLTEXT INDEX fact_fulltext IF NOT EXISTS
FOR ()-[r:RELATION]-() ON EACH [r.fact, r.name]
"""

# =====================================================================
# Aurora additions — city-resilience digital-twin schema
# =====================================================================
# Layered alongside the legacy Aurora (:Entity, :RELATION) graph so
# both the original opinion-simulation pipeline and the new disaster
# simulator share one Neo4j instance. All Aurora nodes use scenario_id
# as their tenant key.

CREATE_SCENARIO_CONSTRAINT = """
CREATE CONSTRAINT scenario_id IF NOT EXISTS
FOR (s:Scenario) REQUIRE s.scenario_id IS UNIQUE
"""

CREATE_DISTRICT_CONSTRAINT = """
CREATE CONSTRAINT district_id IF NOT EXISTS
FOR (d:District) REQUIRE (d.scenario_id, d.district_id) IS UNIQUE
"""

CREATE_BUILDING_CONSTRAINT = """
CREATE CONSTRAINT building_id IF NOT EXISTS
FOR (b:Building) REQUIRE (b.scenario_id, b.building_id) IS UNIQUE
"""

CREATE_HOSPITAL_CONSTRAINT = """
CREATE CONSTRAINT hospital_id IF NOT EXISTS
FOR (h:Hospital) REQUIRE (h.scenario_id, h.hospital_id) IS UNIQUE
"""

CREATE_FIRESTATION_CONSTRAINT = """
CREATE CONSTRAINT firestation_id IF NOT EXISTS
FOR (f:FireStation) REQUIRE (f.scenario_id, f.station_id) IS UNIQUE
"""

CREATE_SHELTER_CONSTRAINT = """
CREATE CONSTRAINT shelter_id IF NOT EXISTS
FOR (sh:Shelter) REQUIRE (sh.scenario_id, sh.shelter_id) IS UNIQUE
"""

# Indexes on h3 cell for spatial queries
CREATE_BUILDING_H3_INDEX = """
CREATE INDEX building_h3 IF NOT EXISTS
FOR (b:Building) ON (b.scenario_id, b.h3_cell)
"""

CREATE_DISTRICT_H3_INDEX = """
CREATE INDEX district_h3 IF NOT EXISTS
FOR (d:District) ON (d.scenario_id, d.h3_cell)
"""

# All schema queries to run on startup
ALL_SCHEMA_QUERIES = [
    # Aurora legacy
    CREATE_GRAPH_UUID_CONSTRAINT,
    CREATE_ENTITY_UUID_CONSTRAINT,
    CREATE_EPISODE_UUID_CONSTRAINT,
    CREATE_ENTITY_VECTOR_INDEX,
    CREATE_RELATION_VECTOR_INDEX,
    CREATE_ENTITY_FULLTEXT_INDEX,
    CREATE_FACT_FULLTEXT_INDEX,
    # Aurora additions
    CREATE_SCENARIO_CONSTRAINT,
    CREATE_DISTRICT_CONSTRAINT,
    CREATE_BUILDING_CONSTRAINT,
    CREATE_HOSPITAL_CONSTRAINT,
    CREATE_FIRESTATION_CONSTRAINT,
    CREATE_SHELTER_CONSTRAINT,
    CREATE_BUILDING_H3_INDEX,
    CREATE_DISTRICT_H3_INDEX,
]
