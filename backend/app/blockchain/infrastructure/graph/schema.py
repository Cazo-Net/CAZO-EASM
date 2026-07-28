"""Cypher schema definitions for Neo4j Blockchain Graph.

Node types:
  :Address          — blockchain address (wallet/contract)
  :Transaction      — on-chain transaction
  :Block            — block on a chain
  :Token            — token contract
  :Contract         — smart contract
  :Label            — entity label (versioned)
  :RiskScore        — computed risk score
  :SanctionList     — sanctions list entry
  :Case             — investigation case
  :Watch            — address watch
  :Alert            — triggered alert
  :Evidence         — evidence item
  :AuditEntry       — audit trail entry

Edge types:
  (:Address)-[:SENT]->(:Transaction)
  (:Address)-[:RECEIVED]->(:Transaction)
  (:Transaction)-[:TO]->(:Address)
  (:Address)-[:OWNS]->(:Token)
  (:Address)-[:DEPLOYED]->(:Contract)
  (:Address)-[:HAS_LABEL]->(:Label)
  (:Address)-[:HAS_RISK]->(:RiskScore)
  (:Case)-[:INVOLVES]->(:Address)
  (:Case)-[:INVOLVES]->(:Transaction)
"""

from __future__ import annotations

import logging

from .neo4j_driver import driver

logger = logging.getLogger(__name__)

# ── Constraints ───────────────────────────────────────────────────────────

CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT address_hash IF NOT EXISTS FOR (a:Address) REQUIRE a.hash IS UNIQUE",
    "CREATE CONSTRAINT tx_hash IF NOT EXISTS FOR (t:Transaction) REQUIRE (t.hash, t.chain) IS NODE KEY",
    "CREATE CONSTRAINT block_id IF NOT EXISTS FOR (b:Block) REQUIRE (b.chain, b.number) IS NODE KEY",
    "CREATE CONSTRAINT label_name IF NOT EXISTS FOR (l:Label) REQUIRE (l.name, l.version) IS NODE KEY",
    "CREATE CONSTRAINT case_id IF NOT EXISTS FOR (c:Case) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT watch_id IF NOT EXISTS FOR (w:Watch) REQUIRE w.id IS UNIQUE",
    "CREATE CONSTRAINT alert_id IF NOT EXISTS FOR (a:Alert) REQUIRE a.id IS UNIQUE",
]

# ── Indexes ───────────────────────────────────────────────────────────────

INDEXES: list[str] = [
    "CREATE INDEX address_chain IF NOT EXISTS FOR (a:Address) ON (a.chain)",
    "CREATE INDEX address_tx_count IF NOT EXISTS FOR (a:Address) ON (a.tx_count)",
    "CREATE INDEX tx_timestamp IF NOT EXISTS FOR (t:Transaction) ON (t.timestamp)",
    "CREATE INDEX tx_from IF NOT EXISTS FOR (t:Transaction) ON (t.from_address)",
    "CREATE INDEX tx_to IF NOT EXISTS FOR (t:Transaction) ON (t.to_address)",
    "CREATE INDEX block_number IF NOT EXISTS FOR (b:Block) ON (b.number)",
    "CREATE INDEX risk_address IF NOT EXISTS FOR (r:RiskScore) ON (r.address)",
    "CREATE INDEX risk_score IF NOT EXISTS FOR (r:RiskScore) ON (r.score)",
]


async def initialize_schema() -> bool:
    if not driver.is_connected:
        logger.warning("Neo4j not available — skipping schema initialization")
        return False

    try:
        for constraint in CONSTRAINTS:
            await driver.run(constraint)
            logger.debug("Constraint ensured: %s", constraint[:60])

        for index in INDEXES:
            await driver.run(index)
            logger.debug("Index ensured: %s", index[:60])

        logger.info("Neo4j schema initialized successfully")
        return True
    except Exception as e:
        logger.warning("Neo4j schema initialization failed: %s", e)
        return False
