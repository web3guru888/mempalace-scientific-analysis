"""Tests for kg_pheromones.py — Stigmergic learning on KG triples."""

import os
import sqlite3
import tempfile

import pytest


# ── Helpers ─────────────────────────────────────────────────────────

def _make_kg_db(tmp_path):
    """Create a minimal KG SQLite database for testing."""
    db_path = os.path.join(str(tmp_path), "test_kg.sqlite3")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS triples (
            id TEXT PRIMARY KEY,
            subject TEXT,
            predicate TEXT,
            object TEXT,
            confidence REAL DEFAULT 0.5,
            valid_from TEXT,
            valid_to TEXT,
            source_closet TEXT,
            source_file TEXT
        )
    """)
    # Insert some test triples
    conn.execute(
        "INSERT INTO triples (id, subject, predicate, object, confidence) VALUES (?, ?, ?, ?, ?)",
        ("t1", "inflation", "causes", "unemployment", 0.8),
    )
    conn.execute(
        "INSERT INTO triples (id, subject, predicate, object, confidence) VALUES (?, ?, ?, ?, ?)",
        ("t2", "gdp", "correlates_with", "inflation", 0.6),
    )
    conn.execute(
        "INSERT INTO triples (id, subject, predicate, object, confidence) VALUES (?, ?, ?, ?, ?)",
        ("t3", "solar_wind", "causes", "aurora", 0.9),
    )
    conn.commit()
    conn.close()
    return db_path


# ── Schema migration tests ──────────────────────────────────────────

class TestPheromoneSchema:
    def test_schema_adds_columns(self, tmp_path):
        """PheromoneManager should add pheromone columns on init."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        _pm = PheromoneManager(db_path)

        # Verify columns exist
        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(triples)").fetchall()}
        conn.close()

        assert "success_pheromone" in cols
        assert "traversal_pheromone" in cols
        assert "recency_pheromone" in cols

    def test_schema_migration_idempotent(self, tmp_path):
        """Calling init twice should not raise."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        PheromoneManager(db_path)
        PheromoneManager(db_path)  # Second init should be safe

    def test_columns_default_to_zero(self, tmp_path):
        """Newly added columns should default to 0.0."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)

        levels = pm.get_pheromone_levels("t1")
        assert levels is not None
        assert levels["success"] == 0.0
        assert levels["traversal"] == 0.0
        assert levels["recency"] == 0.0


# ── Deposit tests ───────────────────────────────────────────────────

class TestPheromoneDeposit:
    def test_deposit_success(self, tmp_path):
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_success("t1", 0.5)

        levels = pm.get_pheromone_levels("t1")
        assert levels["success"] == pytest.approx(0.5)
        assert levels["traversal"] == 0.0
        assert levels["recency"] == 0.0

    def test_deposit_traversal(self, tmp_path):
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_traversal("t2", 0.3)

        levels = pm.get_pheromone_levels("t2")
        assert levels["traversal"] == pytest.approx(0.3)

    def test_deposit_recency(self, tmp_path):
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_recency("t3", 1.0)

        levels = pm.get_pheromone_levels("t3")
        assert levels["recency"] == pytest.approx(1.0)

    def test_deposit_additive(self, tmp_path):
        """Multiple deposits should accumulate."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_success("t1", 0.3)
        pm.deposit_success("t1", 0.4)

        levels = pm.get_pheromone_levels("t1")
        assert levels["success"] == pytest.approx(0.7)

    def test_deposit_on_path_position_weighted(self, tmp_path):
        """Earlier triples in path get higher reward."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_on_path(["t1", "t2", "t3"], base_reward=1.0)

        l1 = pm.get_pheromone_levels("t1")
        l2 = pm.get_pheromone_levels("t2")
        l3 = pm.get_pheromone_levels("t3")

        # t1: reward = 1.0 * (1 - 0/3) = 1.0
        assert l1["success"] == pytest.approx(1.0)
        # t2: reward = 1.0 * (1 - 1/3) ≈ 0.667
        assert l2["success"] == pytest.approx(2.0 / 3, abs=0.01)
        # t3: reward = 1.0 * (1 - 2/3) ≈ 0.333
        assert l3["success"] == pytest.approx(1.0 / 3, abs=0.01)

    def test_deposit_on_empty_path(self, tmp_path):
        """Depositing on empty path should not raise."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_on_path([])  # Should be a no-op

    def test_deposit_on_single_edge_path(self, tmp_path):
        """Single-edge path should get full reward."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_on_path(["t1"], base_reward=0.8)

        levels = pm.get_pheromone_levels("t1")
        # reward = 0.8 * (1 - 0/1) = 0.8
        assert levels["success"] == pytest.approx(0.8)


# ── Decay tests ─────────────────────────────────────────────────────

class TestPheromoneDecay:
    def test_decay_formula(self, tmp_path):
        """Verify τ(t+1) = τ(t) × (1 − ρ)."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_success("t1", 1.0)
        pm.deposit_traversal("t1", 1.0)
        pm.deposit_recency("t1", 1.0)

        pm.decay_all()

        levels = pm.get_pheromone_levels("t1")
        assert levels["success"] == pytest.approx(1.0 * (1 - 0.03), abs=0.001)
        assert levels["traversal"] == pytest.approx(1.0 * (1 - 0.08), abs=0.001)
        assert levels["recency"] == pytest.approx(1.0 * (1 - 0.15), abs=0.001)

    def test_decay_custom_rates(self, tmp_path):
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_success("t1", 1.0)

        pm.decay_all(rates={"success": 0.5, "traversal": 0.5, "recency": 0.5})

        levels = pm.get_pheromone_levels("t1")
        assert levels["success"] == pytest.approx(0.5)

    def test_decay_zero_pheromones_stays_zero(self, tmp_path):
        """Decaying zero pheromones should not go negative."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.decay_all()

        levels = pm.get_pheromone_levels("t1")
        assert levels["success"] >= 0.0
        assert levels["traversal"] >= 0.0
        assert levels["recency"] >= 0.0

    def test_decay_returns_count(self, tmp_path):
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        count = pm.decay_all()
        assert count == 3  # 3 triples in the DB


# ── Modifier tests ──────────────────────────────────────────────────

class TestPheromoneModifier:
    def test_modifier_no_pheromones(self, tmp_path):
        """No pheromones → modifier = 1.0 (no discount)."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)

        mod = pm.get_pheromone_modifier("t1")
        assert mod == pytest.approx(1.0)

    def test_modifier_full_pheromones(self, tmp_path):
        """Full pheromones (all = 1.0) → modifier = 0.5."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_success("t1", 1.0)
        pm.deposit_recency("t1", 1.0)
        pm.deposit_traversal("t1", 1.0)

        mod = pm.get_pheromone_modifier("t1")
        # factor = 0.5*1 + 0.3*1 + 0.2*1 = 1.0
        # modifier = 1.0 - 1.0 * 0.5 = 0.5
        assert mod == pytest.approx(0.5)

    def test_modifier_nonexistent_triple(self, tmp_path):
        """Non-existent triple → modifier = 1.0."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)

        mod = pm.get_pheromone_modifier("nonexistent")
        assert mod == 1.0


# ── Stats tests ─────────────────────────────────────────────────────

class TestPheromoneStats:
    def test_stats_initial(self, tmp_path):
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)

        stats = pm.get_stats()
        assert stats["total_triples"] == 3
        assert stats["success"]["nonzero"] == 0

    def test_stats_after_deposit(self, tmp_path):
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_success("t1", 0.5)
        pm.deposit_success("t2", 1.5)

        stats = pm.get_stats()
        assert stats["success"]["nonzero"] == 2
        assert stats["success"]["max"] == pytest.approx(1.5)
