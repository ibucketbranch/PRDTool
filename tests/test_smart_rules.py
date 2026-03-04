"""Tests for the smart_rules module."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from organizer.smart_rules import (
    CODE_PROJECT_INDICATORS,
    DESKTOP_CONTEXT_PATTERNS,
    MY_DOCUMENT_INDICATORS,
    OTHER_DOCUMENT_INDICATORS,
    PATH_CONTEXT_PATTERNS,
    VA_PATTERNS,
    RuleResult,
    SmartRulesResult,
    apply_smart_rules,
    apply_smart_rules_to_group,
    are_path_contexts_compatible,
    detect_document_ownership,
    detect_path_context,
    is_code_project,
    is_va_document_folder,
    should_consolidate_by_ownership,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_folder():
    """Create a temporary folder for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database with test schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            current_path TEXT,
            ai_category TEXT,
            ai_subcategories TEXT,
            ai_summary TEXT,
            entities TEXT,
            key_dates TEXT,
            folder_hierarchy TEXT,
            pdf_created_date TEXT,
            pdf_modified_date TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE document_locations (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            path TEXT,
            location_type TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    yield db_path

    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def db_with_va_documents(temp_db):
    """Create a database with VA-related documents."""
    conn = sqlite3.connect(temp_db)

    conn.execute(
        """
        INSERT INTO documents (id, filename, current_path, ai_category, ai_subcategories,
            ai_summary, entities, key_dates, folder_hierarchy, pdf_created_date, pdf_modified_date)
        VALUES (1, 'claim_2024.pdf', '/test/VA_Claims/claim_2024.pdf', 'VA Claims',
            '["Veterans Affairs"]', 'VA disability claim', '{"organizations": ["Department of Veterans Affairs"]}',
            '["2024-01-15"]', '["Personal", "VA"]', '2024-01-15', '2024-02-01')
        """
    )

    conn.commit()
    conn.close()

    return temp_db


@pytest.fixture
def db_with_personal_documents(temp_db):
    """Create a database with personal documents containing user name."""
    conn = sqlite3.connect(temp_db)

    # MY documents
    conn.execute(
        """
        INSERT INTO documents (id, filename, current_path, ai_category, ai_subcategories,
            ai_summary, entities, key_dates, folder_hierarchy, pdf_created_date, pdf_modified_date)
        VALUES (1, 'my_resume.pdf', '/test/My_Resume/my_resume.pdf', 'Employment/Resumes',
            '["Employment"]', 'My professional resume', '{"people": ["John Smith"]}',
            '["2024-01-15"]', '["Personal", "Documents"]', '2024-01-15', '2024-02-01')
        """
    )

    # OTHER people's documents
    conn.execute(
        """
        INSERT INTO documents (id, filename, current_path, ai_category, ai_subcategories,
            ai_summary, entities, key_dates, folder_hierarchy, pdf_created_date, pdf_modified_date)
        VALUES (2, 'applicant_resume.pdf', '/test/Received_Resumes/applicant_resume.pdf', 'Employment/Resumes',
            '["Employment"]', 'Job applicant resume', '{"people": ["Jane Doe", "Bob Wilson"]}',
            '["2024-01-15"]', '["Personal", "Documents"]', '2024-01-15', '2024-02-01')
        """
    )

    conn.commit()
    conn.close()

    return temp_db


# =============================================================================
# Test RuleResult
# =============================================================================


class TestRuleResult:
    """Tests for RuleResult dataclass."""

    def test_rule_result_creation(self):
        """Test creating a RuleResult instance."""
        result = RuleResult(
            rule_name="test_rule",
            applies=True,
            action="skip",
            confidence=0.9,
        )
        assert result.rule_name == "test_rule"
        assert result.applies is True
        assert result.action == "skip"
        assert result.confidence == 0.9
        assert result.reasoning == []
        assert result.metadata == {}

    def test_rule_result_with_reasoning(self):
        """Test creating a RuleResult with reasoning."""
        result = RuleResult(
            rule_name="test_rule",
            applies=True,
            action="allow",
            confidence=0.8,
            reasoning=["Found indicator A", "Found indicator B"],
            metadata={"key": "value"},
        )
        assert len(result.reasoning) == 2
        assert result.metadata["key"] == "value"

    def test_rule_result_to_dict(self):
        """Test converting RuleResult to dictionary."""
        result = RuleResult(
            rule_name="test_rule",
            applies=True,
            action="skip",
            confidence=0.9,
            reasoning=["reason1"],
            metadata={"key": "value"},
        )
        d = result.to_dict()
        assert d["rule_name"] == "test_rule"
        assert d["applies"] is True
        assert d["action"] == "skip"
        assert d["confidence"] == 0.9
        assert d["reasoning"] == ["reason1"]
        assert d["metadata"] == {"key": "value"}


# =============================================================================
# Test SmartRulesResult
# =============================================================================


class TestSmartRulesResult:
    """Tests for SmartRulesResult dataclass."""

    def test_smart_rules_result_creation(self):
        """Test creating a SmartRulesResult instance."""
        result = SmartRulesResult(folder_path="/test/folder")
        assert result.folder_path == "/test/folder"
        assert result.should_skip is False
        assert result.should_exclude_from_consolidation is False
        assert result.is_my_document is None
        assert result.rule_results == []
        assert result.overall_reasoning == []

    def test_smart_rules_result_to_dict(self):
        """Test converting SmartRulesResult to dictionary."""
        rule = RuleResult(
            rule_name="test", applies=True, action="allow", confidence=0.5
        )
        result = SmartRulesResult(
            folder_path="/test/folder",
            should_skip=True,
            is_my_document=True,
            rule_results=[rule],
            overall_reasoning=["reason1"],
        )
        d = result.to_dict()
        assert d["folder_path"] == "/test/folder"
        assert d["should_skip"] is True
        assert d["is_my_document"] is True
        assert len(d["rule_results"]) == 1
        assert d["overall_reasoning"] == ["reason1"]


# =============================================================================
# Test Code Project Detection
# =============================================================================


class TestIsCodeProject:
    """Tests for is_code_project function."""

    def test_detects_python_project(self, temp_folder):
        """Test detection of Python project."""
        # Create Python project indicators
        Path(temp_folder, "pyproject.toml").touch()
        Path(temp_folder, "src").mkdir()
        Path(temp_folder, "main.py").touch()

        result = is_code_project(temp_folder)
        assert result.applies is True
        assert result.action == "skip"
        assert result.confidence >= 0.8

    def test_detects_node_project(self, temp_folder):
        """Test detection of Node.js project."""
        Path(temp_folder, "package.json").touch()
        Path(temp_folder, "node_modules").mkdir()

        result = is_code_project(temp_folder)
        assert result.applies is True
        assert result.action == "skip"
        assert result.confidence >= 0.9

    def test_detects_git_repository(self, temp_folder):
        """Test detection of git repository."""
        Path(temp_folder, ".git").mkdir()

        result = is_code_project(temp_folder)
        assert result.applies is True
        assert result.action == "skip"
        assert result.confidence == 1.0

    def test_detects_rust_project(self, temp_folder):
        """Test detection of Rust project."""
        Path(temp_folder, "Cargo.toml").touch()
        Path(temp_folder, "src").mkdir()

        result = is_code_project(temp_folder)
        assert result.applies is True
        assert result.action == "skip"
        assert result.confidence >= 0.9

    def test_detects_go_project(self, temp_folder):
        """Test detection of Go project."""
        Path(temp_folder, "go.mod").touch()
        Path(temp_folder, "main.go").touch()

        result = is_code_project(temp_folder)
        assert result.applies is True
        assert result.action == "skip"
        assert result.confidence == 1.0

    def test_not_code_project_empty_folder(self, temp_folder):
        """Test that empty folder is not a code project."""
        result = is_code_project(temp_folder)
        assert result.applies is False
        assert result.action == "allow"
        assert result.confidence == 0.0

    def test_not_code_project_documents_folder(self, temp_folder):
        """Test that documents folder is not a code project."""
        Path(temp_folder, "resume.pdf").touch()
        Path(temp_folder, "contract.docx").touch()
        Path(temp_folder, "notes.txt").touch()

        result = is_code_project(temp_folder)
        assert result.applies is False
        assert result.action == "allow"

    def test_detects_multiple_code_files(self, temp_folder):
        """Test detection based on multiple code files."""
        for i in range(10):
            Path(temp_folder, f"file{i}.py").touch()

        result = is_code_project(temp_folder)
        assert result.applies is True
        assert result.confidence >= 0.5

    def test_nonexistent_path(self):
        """Test handling of non-existent path."""
        result = is_code_project("/nonexistent/path")
        assert result.applies is False
        assert "not a directory" in result.reasoning[0]


# =============================================================================
# Test VA Document Detection
# =============================================================================


class TestIsVaDocumentFolder:
    """Tests for is_va_document_folder function."""

    def test_detects_va_folder_by_name(self, temp_folder):
        """Test detection of VA folder by name pattern."""
        va_folder = os.path.join(temp_folder, "VA_Claims")
        os.makedirs(va_folder)

        result = is_va_document_folder(va_folder)
        assert result.applies is True
        assert result.action == "exclude_from_consolidation"
        assert result.confidence >= 0.7

    def test_detects_veteran_folder_by_name(self, temp_folder):
        """Test detection of veteran folder by name pattern."""
        veteran_folder = os.path.join(temp_folder, "Veterans_Benefits")
        os.makedirs(veteran_folder)

        result = is_va_document_folder(veteran_folder)
        assert result.applies is True
        assert result.action == "exclude_from_consolidation"

    def test_detects_disability_claim_folder(self, temp_folder):
        """Test detection of disability claim folder."""
        claim_folder = os.path.join(temp_folder, "Disability_Claims")
        os.makedirs(claim_folder)

        result = is_va_document_folder(claim_folder)
        assert result.applies is True
        assert result.action == "exclude_from_consolidation"

    def test_detects_dd214_folder(self, temp_folder):
        """Test detection of DD-214 related folder."""
        dd214_folder = os.path.join(temp_folder, "DD-214_Records")
        os.makedirs(dd214_folder)

        result = is_va_document_folder(dd214_folder)
        assert result.applies is True
        assert result.action == "exclude_from_consolidation"

    def test_not_va_folder_regular_documents(self, temp_folder):
        """Test that regular documents folder is not VA."""
        docs_folder = os.path.join(temp_folder, "Documents")
        os.makedirs(docs_folder)

        result = is_va_document_folder(docs_folder)
        assert result.applies is False
        assert result.action == "allow"

    def test_detects_va_by_database_category(self, db_with_va_documents):
        """Test detection of VA folder by database AI category."""
        conn = sqlite3.connect(db_with_va_documents)

        result = is_va_document_folder("/test/VA_Claims", conn=conn)
        assert result.applies is True
        assert result.action == "exclude_from_consolidation"

        conn.close()

    def test_va_patterns_exist(self):
        """Test that VA patterns are properly defined."""
        assert "folder_names" in VA_PATTERNS
        assert "categories" in VA_PATTERNS
        assert len(VA_PATTERNS["folder_names"]) > 0
        assert len(VA_PATTERNS["categories"]) > 0


# =============================================================================
# Test Document Ownership Detection
# =============================================================================


class TestDetectDocumentOwnership:
    """Tests for detect_document_ownership function."""

    def test_detects_my_document_by_folder_name(self, temp_folder):
        """Test detection of MY document by folder name pattern."""
        my_folder = os.path.join(temp_folder, "My_Documents")
        os.makedirs(my_folder)

        result = detect_document_ownership(my_folder)
        assert result.metadata["is_my_document"] is True

    def test_detects_personal_folder(self, temp_folder):
        """Test detection of personal folder."""
        personal_folder = os.path.join(temp_folder, "Personal_Files")
        os.makedirs(personal_folder)

        result = detect_document_ownership(personal_folder)
        assert result.metadata["is_my_document"] is True

    def test_detects_other_documents_by_folder_name(self, temp_folder):
        """Test detection of OTHER documents by folder name pattern."""
        others_folder = os.path.join(temp_folder, "Others_Resumes")
        os.makedirs(others_folder)

        result = detect_document_ownership(others_folder)
        assert result.metadata["is_my_document"] is False

    def test_detects_received_documents(self, temp_folder):
        """Test detection of received documents (OTHER)."""
        received_folder = os.path.join(temp_folder, "Received_Applications")
        os.makedirs(received_folder)

        result = detect_document_ownership(received_folder)
        assert result.metadata["is_my_document"] is False

    def test_detects_client_documents(self, temp_folder):
        """Test detection of client documents (OTHER)."""
        client_folder = os.path.join(temp_folder, "Client_Files")
        os.makedirs(client_folder)

        result = detect_document_ownership(client_folder)
        assert result.metadata["is_my_document"] is False

    def test_unknown_ownership_neutral_folder(self, temp_folder):
        """Test that neutral folder has unknown ownership."""
        docs_folder = os.path.join(temp_folder, "Documents")
        os.makedirs(docs_folder)

        result = detect_document_ownership(docs_folder)
        assert result.metadata["is_my_document"] is None

    def test_detects_my_by_user_name_match(self, db_with_personal_documents):
        """Test detection of MY by matching user name in entities."""
        conn = sqlite3.connect(db_with_personal_documents)

        result = detect_document_ownership(
            "/test/My_Resume",
            user_name="John Smith",
            conn=conn,
        )
        assert result.metadata["is_my_document"] is True

        conn.close()

    def test_detects_other_by_different_names(self, db_with_personal_documents):
        """Test detection of OTHER by non-matching names in entities."""
        conn = sqlite3.connect(db_with_personal_documents)

        result = detect_document_ownership(
            "/test/Received_Resumes",
            user_name="John Smith",
            conn=conn,
        )
        # The folder name pattern "Received_" indicates OTHER
        assert result.metadata["is_my_document"] is False

        conn.close()


# =============================================================================
# Test Ownership Consolidation Check
# =============================================================================


class TestShouldConsolidateByOwnership:
    """Tests for should_consolidate_by_ownership function."""

    def test_allows_consolidation_same_ownership_my(self, temp_folder):
        """Test that MY folders can consolidate together."""
        my_folder1 = os.path.join(temp_folder, "My_Resume")
        my_folder2 = os.path.join(temp_folder, "My_CV")
        os.makedirs(my_folder1)
        os.makedirs(my_folder2)

        result = should_consolidate_by_ownership(my_folder1, my_folder2)
        assert result.action == "allow"

    def test_allows_consolidation_same_ownership_other(self, temp_folder):
        """Test that OTHER folders can consolidate together."""
        other_folder1 = os.path.join(temp_folder, "Client_Documents")
        other_folder2 = os.path.join(temp_folder, "Received_Files")
        os.makedirs(other_folder1)
        os.makedirs(other_folder2)

        result = should_consolidate_by_ownership(other_folder1, other_folder2)
        assert result.action == "allow"

    def test_blocks_consolidation_different_ownership(self, temp_folder):
        """Test that MY and OTHER folders cannot consolidate."""
        my_folder = os.path.join(temp_folder, "My_Resume")
        other_folder = os.path.join(temp_folder, "Received_Resumes")
        os.makedirs(my_folder)
        os.makedirs(other_folder)

        result = should_consolidate_by_ownership(my_folder, other_folder)
        assert result.action == "exclude_from_consolidation"
        assert "Cannot consolidate MY documents with OTHER" in result.reasoning[0]

    def test_allows_unknown_ownership(self, temp_folder):
        """Test that unknown ownership folders are allowed."""
        folder1 = os.path.join(temp_folder, "Documents")
        folder2 = os.path.join(temp_folder, "Files")
        os.makedirs(folder1)
        os.makedirs(folder2)

        result = should_consolidate_by_ownership(folder1, folder2)
        assert result.action == "allow"


# =============================================================================
# Test Apply Smart Rules
# =============================================================================


class TestApplySmartRules:
    """Tests for apply_smart_rules function."""

    def test_applies_all_rules(self, temp_folder):
        """Test that all rules are applied."""
        docs_folder = os.path.join(temp_folder, "Documents")
        os.makedirs(docs_folder)

        result = apply_smart_rules(docs_folder)
        assert result.folder_path == docs_folder
        assert len(result.rule_results) >= 3  # code, va, ownership

    def test_skips_code_project(self, temp_folder):
        """Test that code projects are marked to skip."""
        code_folder = os.path.join(temp_folder, "MyProject")
        os.makedirs(code_folder)
        Path(code_folder, "package.json").touch()
        Path(code_folder, ".git").mkdir()

        result = apply_smart_rules(code_folder)
        assert result.should_skip is True
        assert "Code project detected" in result.overall_reasoning[0]

    def test_excludes_va_documents(self, temp_folder):
        """Test that VA documents are marked for exclusion."""
        va_folder = os.path.join(temp_folder, "VA_Claims")
        os.makedirs(va_folder)

        result = apply_smart_rules(va_folder)
        assert result.should_exclude_from_consolidation is True
        assert "VA document folder" in result.overall_reasoning[0]

    def test_detects_my_documents(self, temp_folder):
        """Test that MY documents are detected."""
        my_folder = os.path.join(temp_folder, "My_Files")
        os.makedirs(my_folder)

        result = apply_smart_rules(my_folder)
        assert result.is_my_document is True


# =============================================================================
# Test Apply Smart Rules to Group
# =============================================================================


class TestApplySmartRulesToGroup:
    """Tests for apply_smart_rules_to_group function."""

    def test_allows_consolidation_similar_folders(self, temp_folder):
        """Test that similar folders can consolidate."""
        folder1 = os.path.join(temp_folder, "Resume")
        folder2 = os.path.join(temp_folder, "Resumes")
        os.makedirs(folder1)
        os.makedirs(folder2)

        should_consolidate, reasoning, results = apply_smart_rules_to_group(
            [folder1, folder2]
        )
        assert should_consolidate is True
        assert "All smart rules passed" in reasoning

    def test_blocks_code_project_in_group(self, temp_folder):
        """Test that code project blocks group consolidation."""
        docs_folder = os.path.join(temp_folder, "Documents")
        code_folder = os.path.join(temp_folder, "MyProject")
        os.makedirs(docs_folder)
        os.makedirs(code_folder)
        Path(code_folder, "package.json").touch()
        Path(code_folder, ".git").mkdir()

        should_consolidate, reasoning, results = apply_smart_rules_to_group(
            [docs_folder, code_folder]
        )
        assert should_consolidate is False
        assert any("code project" in r.lower() for r in reasoning)

    def test_blocks_va_documents_in_group(self, temp_folder):
        """Test that VA documents block group consolidation."""
        docs_folder = os.path.join(temp_folder, "Documents")
        va_folder = os.path.join(temp_folder, "VA_Claims")
        os.makedirs(docs_folder)
        os.makedirs(va_folder)

        should_consolidate, reasoning, results = apply_smart_rules_to_group(
            [docs_folder, va_folder]
        )
        assert should_consolidate is False
        assert any("VA documents" in r for r in reasoning)

    def test_blocks_mixed_ownership_in_group(self, temp_folder):
        """Test that mixed ownership blocks group consolidation."""
        my_folder = os.path.join(temp_folder, "My_Files")
        other_folder = os.path.join(temp_folder, "Received_Files")
        os.makedirs(my_folder)
        os.makedirs(other_folder)

        should_consolidate, reasoning, results = apply_smart_rules_to_group(
            [my_folder, other_folder]
        )
        assert should_consolidate is False
        assert any("MY documents" in r and "OTHER" in r for r in reasoning)

    def test_returns_individual_results(self, temp_folder):
        """Test that individual results are returned for each folder."""
        folder1 = os.path.join(temp_folder, "Folder1")
        folder2 = os.path.join(temp_folder, "Folder2")
        os.makedirs(folder1)
        os.makedirs(folder2)

        _, _, results = apply_smart_rules_to_group([folder1, folder2])
        assert folder1 in results
        assert folder2 in results
        assert isinstance(results[folder1], SmartRulesResult)
        assert isinstance(results[folder2], SmartRulesResult)


# =============================================================================
# Test Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_code_project_indicators_files(self):
        """Test that code project file indicators are defined."""
        assert "package.json" in CODE_PROJECT_INDICATORS["files"]
        assert "pyproject.toml" in CODE_PROJECT_INDICATORS["files"]
        assert "Cargo.toml" in CODE_PROJECT_INDICATORS["files"]

    def test_code_project_indicators_folders(self):
        """Test that code project folder indicators are defined."""
        assert ".git" in CODE_PROJECT_INDICATORS["folders"]
        assert "node_modules" in CODE_PROJECT_INDICATORS["folders"]
        assert "__pycache__" in CODE_PROJECT_INDICATORS["folders"]

    def test_code_project_indicators_extensions(self):
        """Test that code file extensions are defined."""
        assert ".py" in CODE_PROJECT_INDICATORS["extensions"]
        assert ".js" in CODE_PROJECT_INDICATORS["extensions"]
        assert ".rs" in CODE_PROJECT_INDICATORS["extensions"]

    def test_my_document_indicators(self):
        """Test that MY document indicators are defined."""
        assert len(MY_DOCUMENT_INDICATORS) > 0

    def test_other_document_indicators(self):
        """Test that OTHER document indicators are defined."""
        assert len(OTHER_DOCUMENT_INDICATORS) > 0

    def test_va_patterns(self):
        """Test that VA patterns are properly structured."""
        assert "folder_names" in VA_PATTERNS
        assert "categories" in VA_PATTERNS
        assert len(VA_PATTERNS["folder_names"]) > 0
        assert len(VA_PATTERNS["categories"]) > 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for smart rules."""

    def test_full_workflow_resume_consolidation(self, temp_folder):
        """Test full workflow for resume folder consolidation."""
        # Create MY resume folders
        my_resume = os.path.join(temp_folder, "My_Resume")
        my_cv = os.path.join(temp_folder, "Personal_CV")
        os.makedirs(my_resume)
        os.makedirs(my_cv)

        # Both should be allowed to consolidate
        should_consolidate, reasoning, _ = apply_smart_rules_to_group(
            [my_resume, my_cv]
        )
        assert should_consolidate is True

    def test_full_workflow_va_exclusion(self, temp_folder):
        """Test that VA folders are properly excluded."""
        # Create folders
        docs = os.path.join(temp_folder, "Documents")
        va_claims = os.path.join(temp_folder, "VA_Claims")
        va_benefits = os.path.join(temp_folder, "Veterans_Benefits")
        os.makedirs(docs)
        os.makedirs(va_claims)
        os.makedirs(va_benefits)

        # Docs with VA should not consolidate
        should_consolidate, _, _ = apply_smart_rules_to_group([docs, va_claims])
        assert should_consolidate is False

        # Two VA folders should also not consolidate (both excluded)
        should_consolidate, _, _ = apply_smart_rules_to_group([va_claims, va_benefits])
        assert should_consolidate is False

    def test_full_workflow_code_project_skip(self, temp_folder):
        """Test that code projects are properly skipped."""
        # Create a code project
        project = os.path.join(temp_folder, "MyApp")
        os.makedirs(project)
        Path(project, "package.json").touch()
        Path(project, ".git").mkdir()
        Path(project, "src").mkdir()

        # Apply rules
        result = apply_smart_rules(project)
        assert result.should_skip is True

        # In a group, should block consolidation
        docs = os.path.join(temp_folder, "Documents")
        os.makedirs(docs)

        should_consolidate, _, _ = apply_smart_rules_to_group([project, docs])
        assert should_consolidate is False

    def test_full_workflow_mixed_ownership_block(self, temp_folder):
        """Test that mixed ownership blocks consolidation."""
        # Create folders with different ownership
        my_folder = os.path.join(temp_folder, "My_Documents")
        received = os.path.join(temp_folder, "Received_Documents")
        client = os.path.join(temp_folder, "Client_Files")
        os.makedirs(my_folder)
        os.makedirs(received)
        os.makedirs(client)

        # MY + OTHER should not consolidate
        should_consolidate, _, _ = apply_smart_rules_to_group([my_folder, received])
        assert should_consolidate is False

        # OTHER + OTHER should consolidate
        should_consolidate, _, _ = apply_smart_rules_to_group([received, client])
        assert should_consolidate is True


# =============================================================================
# Test Path Context Detection
# =============================================================================


class TestDetectPathContext:
    """Tests for detect_path_context function."""

    def test_detects_microsoft_context(self, temp_folder):
        """Test detection of Microsoft path context."""
        ms_folder = os.path.join(temp_folder, "OneDrive", "Documents")
        os.makedirs(ms_folder)

        result = detect_path_context(ms_folder)
        assert "microsoft" in result.metadata["detected_contexts"]

    def test_detects_macos_context(self, temp_folder):
        """Test detection of macOS path context."""
        mac_folder = os.path.join(temp_folder, "iCloud", "Documents")
        os.makedirs(mac_folder)

        result = detect_path_context(mac_folder)
        assert "macos" in result.metadata["detected_contexts"]

    def test_detects_google_drive_context(self, temp_folder):
        """Test detection of Google Drive path context."""
        gdrive_folder = os.path.join(temp_folder, "Google Drive", "Documents")
        os.makedirs(gdrive_folder)

        result = detect_path_context(gdrive_folder)
        assert "google" in result.metadata["detected_contexts"]

    def test_detects_dropbox_context(self, temp_folder):
        """Test detection of Dropbox path context."""
        dropbox_folder = os.path.join(temp_folder, "Dropbox", "Files")
        os.makedirs(dropbox_folder)

        result = detect_path_context(dropbox_folder)
        assert "dropbox" in result.metadata["detected_contexts"]

    def test_detects_work_context(self, temp_folder):
        """Test detection of work path context."""
        work_folder = os.path.join(temp_folder, "Work", "Projects")
        os.makedirs(work_folder)

        result = detect_path_context(work_folder)
        assert "work" in result.metadata["detected_contexts"]

    def test_detects_personal_context(self, temp_folder):
        """Test detection of personal path context."""
        personal_folder = os.path.join(temp_folder, "Personal", "Documents")
        os.makedirs(personal_folder)

        result = detect_path_context(personal_folder)
        assert "personal" in result.metadata["detected_contexts"]

    def test_detects_microsoft_desktop_context(self, temp_folder):
        """Test detection of Microsoft Desktop path context."""
        ms_desktop = os.path.join(temp_folder, "OneDrive", "Desktop")
        os.makedirs(ms_desktop)

        result = detect_path_context(ms_desktop)
        assert "microsoft_desktop" in result.metadata["detected_contexts"]

    def test_detects_macos_desktop_context(self, temp_folder):
        """Test detection of macOS Desktop path context."""
        mac_desktop = os.path.join(temp_folder, "iCloud", "Desktop")
        os.makedirs(mac_desktop)

        result = detect_path_context(mac_desktop)
        assert "macos_desktop" in result.metadata["detected_contexts"]

    def test_no_context_for_neutral_folder(self, temp_folder):
        """Test that neutral folder has no specific context."""
        neutral_folder = os.path.join(temp_folder, "Documents")
        os.makedirs(neutral_folder)

        result = detect_path_context(neutral_folder)
        assert len(result.metadata["detected_contexts"]) == 0

    def test_multiple_contexts_detected(self, temp_folder):
        """Test detection of multiple path contexts."""
        folder = os.path.join(temp_folder, "OneDrive", "Work", "Projects")
        os.makedirs(folder)

        result = detect_path_context(folder)
        contexts = set(result.metadata["detected_contexts"])
        assert "microsoft" in contexts
        assert "work" in contexts


# =============================================================================
# Test Path Context Compatibility
# =============================================================================


class TestArePathContextsCompatible:
    """Tests for are_path_contexts_compatible function."""

    def test_microsoft_vs_macos_desktop_incompatible(self, temp_folder):
        """Test that Microsoft Desktop and macOS Desktop are incompatible."""
        ms_desktop = os.path.join(temp_folder, "Microsoft", "Desktop")
        mac_desktop = os.path.join(temp_folder, "iCloud", "Desktop")
        os.makedirs(ms_desktop)
        os.makedirs(mac_desktop)

        result = are_path_contexts_compatible(ms_desktop, mac_desktop)
        assert result.action == "exclude_from_consolidation"
        assert "desktop_source" in result.metadata.get("conflict_type", "")

    def test_microsoft_vs_macos_system_incompatible(self, temp_folder):
        """Test that Microsoft and macOS system contexts are incompatible."""
        ms_folder = os.path.join(temp_folder, "OneDrive", "Documents")
        mac_folder = os.path.join(temp_folder, "iCloud", "Documents")
        os.makedirs(ms_folder)
        os.makedirs(mac_folder)

        result = are_path_contexts_compatible(ms_folder, mac_folder)
        assert result.action == "exclude_from_consolidation"
        assert "system_source" in result.metadata.get("conflict_type", "")

    def test_work_vs_personal_incompatible(self, temp_folder):
        """Test that work and personal contexts are incompatible."""
        work_folder = os.path.join(temp_folder, "Work", "Documents")
        personal_folder = os.path.join(temp_folder, "Personal", "Documents")
        os.makedirs(work_folder)
        os.makedirs(personal_folder)

        result = are_path_contexts_compatible(work_folder, personal_folder)
        assert result.action == "exclude_from_consolidation"
        assert "work_personal" in result.metadata.get("conflict_type", "")

    def test_same_context_compatible(self, temp_folder):
        """Test that same context folders are compatible."""
        ms_folder1 = os.path.join(temp_folder, "OneDrive", "Documents")
        ms_folder2 = os.path.join(temp_folder, "OneDrive", "Files")
        os.makedirs(ms_folder1)
        os.makedirs(ms_folder2)

        result = are_path_contexts_compatible(ms_folder1, ms_folder2)
        assert result.action == "allow"

    def test_neutral_folders_compatible(self, temp_folder):
        """Test that neutral folders are compatible."""
        folder1 = os.path.join(temp_folder, "Documents")
        folder2 = os.path.join(temp_folder, "Files")
        os.makedirs(folder1)
        os.makedirs(folder2)

        result = are_path_contexts_compatible(folder1, folder2)
        assert result.action == "allow"

    def test_google_vs_dropbox_incompatible(self, temp_folder):
        """Test that Google Drive and Dropbox are incompatible."""
        gdrive = os.path.join(temp_folder, "Google Drive", "Documents")
        dropbox = os.path.join(temp_folder, "Dropbox", "Documents")
        os.makedirs(gdrive)
        os.makedirs(dropbox)

        result = are_path_contexts_compatible(gdrive, dropbox)
        assert result.action == "exclude_from_consolidation"


# =============================================================================
# Test Smart Rules Result with Path Context
# =============================================================================


class TestSmartRulesResultPathContext:
    """Tests for SmartRulesResult with path context field."""

    def test_smart_rules_result_has_path_contexts(self):
        """Test that SmartRulesResult includes path_contexts field."""
        result = SmartRulesResult(
            folder_path="/test/folder",
            path_contexts=["microsoft", "work"],
        )
        assert result.path_contexts == ["microsoft", "work"]

    def test_smart_rules_result_to_dict_includes_path_contexts(self):
        """Test that to_dict includes path_contexts."""
        result = SmartRulesResult(
            folder_path="/test/folder",
            path_contexts=["macos", "personal"],
        )
        d = result.to_dict()
        assert "path_contexts" in d
        assert d["path_contexts"] == ["macos", "personal"]


# =============================================================================
# Test Apply Smart Rules with Path Context
# =============================================================================


class TestApplySmartRulesWithPathContext:
    """Tests for apply_smart_rules with path context detection."""

    def test_apply_smart_rules_detects_path_context(self, temp_folder):
        """Test that apply_smart_rules detects path context."""
        ms_folder = os.path.join(temp_folder, "OneDrive", "Documents")
        os.makedirs(ms_folder)

        result = apply_smart_rules(ms_folder)
        assert "microsoft" in result.path_contexts
        assert len(result.rule_results) >= 4  # code, va, ownership, path_context

    def test_apply_smart_rules_includes_path_context_reasoning(self, temp_folder):
        """Test that apply_smart_rules includes path context in reasoning."""
        work_folder = os.path.join(temp_folder, "Work", "Projects")
        os.makedirs(work_folder)

        result = apply_smart_rules(work_folder)
        path_reasoning = [r for r in result.overall_reasoning if "Path context" in r]
        assert len(path_reasoning) > 0


# =============================================================================
# Test Apply Smart Rules to Group with Path Context
# =============================================================================


class TestApplySmartRulesToGroupWithPathContext:
    """Tests for apply_smart_rules_to_group with path context checking."""

    def test_blocks_different_desktop_sources(self, temp_folder):
        """Test that different desktop sources block consolidation."""
        ms_desktop = os.path.join(temp_folder, "OneDrive", "Desktop")
        mac_desktop = os.path.join(temp_folder, "iCloud", "Desktop")
        os.makedirs(ms_desktop)
        os.makedirs(mac_desktop)

        should_consolidate, reasoning, _ = apply_smart_rules_to_group(
            [ms_desktop, mac_desktop]
        )
        assert should_consolidate is False
        assert any(
            "desktop" in r.lower() or "microsoft" in r.lower() for r in reasoning
        )

    def test_blocks_different_system_sources(self, temp_folder):
        """Test that different system sources block consolidation."""
        ms_folder = os.path.join(temp_folder, "OneDrive", "Documents")
        mac_folder = os.path.join(temp_folder, "iCloud", "Documents")
        os.makedirs(ms_folder)
        os.makedirs(mac_folder)

        should_consolidate, reasoning, _ = apply_smart_rules_to_group(
            [ms_folder, mac_folder]
        )
        assert should_consolidate is False

    def test_blocks_work_vs_personal(self, temp_folder):
        """Test that work vs personal blocks consolidation."""
        work_folder = os.path.join(temp_folder, "Work", "Files")
        personal_folder = os.path.join(temp_folder, "Personal", "Files")
        os.makedirs(work_folder)
        os.makedirs(personal_folder)

        should_consolidate, reasoning, _ = apply_smart_rules_to_group(
            [work_folder, personal_folder]
        )
        assert should_consolidate is False
        assert any("work" in r.lower() and "personal" in r.lower() for r in reasoning)

    def test_allows_same_source_folders(self, temp_folder):
        """Test that same source folders can consolidate."""
        ms_folder1 = os.path.join(temp_folder, "OneDrive", "Resume")
        ms_folder2 = os.path.join(temp_folder, "OneDrive", "Resumes")
        os.makedirs(ms_folder1)
        os.makedirs(ms_folder2)

        should_consolidate, reasoning, _ = apply_smart_rules_to_group(
            [ms_folder1, ms_folder2]
        )
        assert should_consolidate is True
        assert "All smart rules passed" in reasoning


# =============================================================================
# Test Constants for Path Context
# =============================================================================


class TestPathContextConstants:
    """Tests for path context constants."""

    def test_path_context_patterns_defined(self):
        """Test that PATH_CONTEXT_PATTERNS is properly defined."""
        assert "microsoft" in PATH_CONTEXT_PATTERNS
        assert "macos" in PATH_CONTEXT_PATTERNS
        assert "google" in PATH_CONTEXT_PATTERNS
        assert "dropbox" in PATH_CONTEXT_PATTERNS
        assert "work" in PATH_CONTEXT_PATTERNS
        assert "personal" in PATH_CONTEXT_PATTERNS

    def test_desktop_context_patterns_defined(self):
        """Test that DESKTOP_CONTEXT_PATTERNS is properly defined."""
        assert "microsoft_desktop" in DESKTOP_CONTEXT_PATTERNS
        assert "macos_desktop" in DESKTOP_CONTEXT_PATTERNS

    def test_microsoft_patterns_include_common_terms(self):
        """Test that Microsoft patterns include common terms."""
        patterns = PATH_CONTEXT_PATTERNS["microsoft"]
        pattern_str = " ".join(patterns)
        assert "onedrive" in pattern_str
        assert "windows" in pattern_str or "microsoft" in pattern_str

    def test_macos_patterns_include_common_terms(self):
        """Test that macOS patterns include common terms."""
        patterns = PATH_CONTEXT_PATTERNS["macos"]
        pattern_str = " ".join(patterns)
        assert "icloud" in pattern_str
        assert "macos" in pattern_str or "apple" in pattern_str


# =============================================================================
# Integration Tests for Path Context Rules
# =============================================================================


class TestPathContextIntegration:
    """Integration tests for path context rules."""

    def test_prd_example_desktop_different_sources(self, temp_folder):
        """Test PRD example: Desktop (Microsoft) vs Desktop 2 (macOS)."""
        # Simulate PRD example: Desktop folders from different sources
        ms_desktop = os.path.join(temp_folder, "Microsoft_OneDrive", "Desktop")
        mac_desktop = os.path.join(temp_folder, "iCloud", "Desktop 2")
        os.makedirs(ms_desktop)
        os.makedirs(mac_desktop)

        should_consolidate, reasoning, _ = apply_smart_rules_to_group(
            [ms_desktop, mac_desktop]
        )
        assert should_consolidate is False
        # Should mention the conflict
        full_reasoning = " ".join(reasoning).lower()
        assert "cannot consolidate" in full_reasoning

    def test_same_source_different_names_can_consolidate(self, temp_folder):
        """Test that same source folders with different names can consolidate."""
        # Both from OneDrive - should be able to consolidate
        folder1 = os.path.join(temp_folder, "OneDrive", "Tax_Docs")
        folder2 = os.path.join(temp_folder, "OneDrive", "Tax_Documents")
        os.makedirs(folder1)
        os.makedirs(folder2)

        should_consolidate, _, _ = apply_smart_rules_to_group([folder1, folder2])
        assert should_consolidate is True

    def test_archive_context_detection(self, temp_folder):
        """Test detection of archive context."""
        archive_folder = os.path.join(temp_folder, "Archive", "Old_Files")
        os.makedirs(archive_folder)

        result = detect_path_context(archive_folder)
        assert "archive" in result.metadata["detected_contexts"]

    def test_full_workflow_multiple_contexts(self, temp_folder):
        """Test full workflow with multiple context checks."""
        # Create various folders
        work_ms = os.path.join(temp_folder, "OneDrive", "Work", "Projects")
        personal_mac = os.path.join(temp_folder, "iCloud", "Personal", "Documents")
        neutral = os.path.join(temp_folder, "Documents")
        os.makedirs(work_ms)
        os.makedirs(personal_mac)
        os.makedirs(neutral)

        # Work/Microsoft vs Personal/macOS should not consolidate
        should_consolidate, _, _ = apply_smart_rules_to_group([work_ms, personal_mac])
        assert should_consolidate is False

        # Neutral folder should consolidate with other neutral
        neutral2 = os.path.join(temp_folder, "Files")
        os.makedirs(neutral2)
        should_consolidate, _, _ = apply_smart_rules_to_group([neutral, neutral2])
        assert should_consolidate is True
