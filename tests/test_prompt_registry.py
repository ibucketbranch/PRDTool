"""Tests for the prompt_registry module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from organizer.prompt_registry import (
    DEFAULT_PROMPTS,
    LoadedPrompt,
    PromptMetadata,
    PromptRegistry,
    get_prompt,
    list_available_prompts,
)


class TestPromptMetadata:
    """Tests for the PromptMetadata dataclass."""

    def test_create_metadata(self) -> None:
        """Test creating prompt metadata."""
        metadata = PromptMetadata(
            name="classify_file",
            version="1.0.0",
            last_modified="2024-01-15",
            description="Classify a file into a category.",
        )
        assert metadata.name == "classify_file"
        assert metadata.version == "1.0.0"
        assert metadata.last_modified == "2024-01-15"
        assert metadata.description == "Classify a file into a category."

    def test_metadata_with_empty_values(self) -> None:
        """Test metadata with empty values."""
        metadata = PromptMetadata(
            name="test",
            version="",
            last_modified="",
            description="",
        )
        assert metadata.name == "test"
        assert metadata.version == ""
        assert metadata.last_modified == ""
        assert metadata.description == ""


class TestLoadedPrompt:
    """Tests for the LoadedPrompt dataclass."""

    def test_create_loaded_prompt(self) -> None:
        """Test creating a loaded prompt."""
        metadata = PromptMetadata(
            name="test",
            version="1.0.0",
            last_modified="2024-01-15",
            description="Test prompt.",
        )
        prompt = LoadedPrompt(
            metadata=metadata,
            template="Hello {name}!",
            source_path=Path("/test/path.txt"),
        )
        assert prompt.metadata == metadata
        assert prompt.template == "Hello {name}!"
        assert prompt.source_path == Path("/test/path.txt")

    def test_loaded_prompt_with_no_source(self) -> None:
        """Test loaded prompt with no source path (from defaults)."""
        metadata = PromptMetadata(
            name="default",
            version="1.0.0",
            last_modified="",
            description="Default prompt.",
        )
        prompt = LoadedPrompt(
            metadata=metadata,
            template="Default template",
            source_path=None,
        )
        assert prompt.source_path is None


class TestPromptRegistry:
    """Tests for the PromptRegistry class."""

    def test_init_with_default_dir(self) -> None:
        """Test initialization with default directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / ".organizer" / "prompts"
            registry = PromptRegistry(prompts_dir=prompts_dir)
            assert registry.prompts_dir == prompts_dir

    def test_init_creates_directory(self) -> None:
        """Test that init creates prompts directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "new_prompts"
            assert not prompts_dir.exists()
            _registry = PromptRegistry(prompts_dir=prompts_dir)
            assert prompts_dir.exists()
            # Should have created default prompts
            assert len(list(prompts_dir.glob("*.txt"))) > 0

    def test_init_creates_default_prompts(self) -> None:
        """Test that default prompts are created on init."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            _registry = PromptRegistry(prompts_dir=prompts_dir)

            # All default prompts should exist
            for name in DEFAULT_PROMPTS:
                filepath = prompts_dir / f"{name}.txt"
                assert filepath.exists(), f"Default prompt '{name}' not created"

    def test_get_prompt_with_variables(self) -> None:
        """Test getting a prompt with variable substitution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            # Create a test prompt
            (prompts_dir / "test.txt").write_text(
                "# Prompt: test\n# Version: 1.0.0\n\nHello {name}!"
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)
            result = registry.get("test", name="World")
            assert result == "Hello World!"

    def test_get_prompt_multiple_variables(self) -> None:
        """Test getting a prompt with multiple variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "multi.txt").write_text(
                "# Prompt: multi\n\n{greeting}, {name}! Your {item} is ready."
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)
            result = registry.get("multi", greeting="Hello", name="Alice", item="order")
            assert result == "Hello, Alice! Your order is ready."

    def test_get_prompt_missing_variable_raises(self) -> None:
        """Test that missing variables raise KeyError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "vars.txt").write_text(
                "# Prompt: vars\n\nHello {name}, your {item}!"
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)
            with pytest.raises(KeyError) as excinfo:
                registry.get("vars", name="Bob")  # Missing 'item'

            assert "item" in str(excinfo.value)

    def test_get_prompt_not_found_raises(self) -> None:
        """Test that missing prompts raise FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            registry = PromptRegistry(prompts_dir=prompts_dir)
            with pytest.raises(FileNotFoundError) as excinfo:
                registry.get("nonexistent")

            assert "nonexistent" in str(excinfo.value)

    def test_get_raw_template(self) -> None:
        """Test getting raw template without substitution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "raw.txt").write_text(
                "# Prompt: raw\n\nTemplate with {placeholder}"
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)
            result = registry.get_raw("raw")
            assert result == "Template with {placeholder}"

    def test_get_metadata(self) -> None:
        """Test getting prompt metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "meta.txt").write_text(
                "# Prompt: meta\n"
                "# Version: 2.0.0\n"
                "# Last-Modified: 2024-03-01\n"
                "# Description: Test metadata parsing.\n"
                "\nContent here"
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)
            metadata = registry.get_metadata("meta")

            assert metadata.name == "meta"
            assert metadata.version == "2.0.0"
            assert metadata.last_modified == "2024-03-01"
            assert metadata.description == "Test metadata parsing."

    def test_get_metadata_fills_name_from_filename(self) -> None:
        """Test that metadata name is filled from filename if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            # No Prompt: header
            (prompts_dir / "named.txt").write_text(
                "# Version: 1.0.0\n\nContent"
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)
            metadata = registry.get_metadata("named")
            assert metadata.name == "named"

    def test_list_prompts(self) -> None:
        """Test listing available prompts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            # Create some prompts
            (prompts_dir / "first.txt").write_text("# Prompt: first\n\nFirst")
            (prompts_dir / "second.txt").write_text("# Prompt: second\n\nSecond")

            registry = PromptRegistry(prompts_dir=prompts_dir)
            prompts = registry.list_prompts()

            assert "first" in prompts
            assert "second" in prompts
            # Should also include defaults
            for default_name in DEFAULT_PROMPTS:
                assert default_name in prompts

    def test_list_prompts_sorted(self) -> None:
        """Test that listed prompts are sorted alphabetically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "zebra.txt").write_text("# Prompt: zebra\n\nZ")
            (prompts_dir / "apple.txt").write_text("# Prompt: apple\n\nA")

            registry = PromptRegistry(prompts_dir=prompts_dir)
            prompts = registry.list_prompts()

            # First should be "apple" alphabetically (before defaults)
            assert prompts == sorted(prompts)

    def test_has_prompt_in_files(self) -> None:
        """Test checking if prompt exists in files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "exists.txt").write_text("# Prompt: exists\n\nContent")

            registry = PromptRegistry(prompts_dir=prompts_dir)
            assert registry.has_prompt("exists")
            assert not registry.has_prompt("does_not_exist")

    def test_has_prompt_in_defaults(self) -> None:
        """Test checking if prompt exists in defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            registry = PromptRegistry(prompts_dir=prompts_dir)

            # Default prompts should exist
            assert registry.has_prompt("classify_file")
            assert registry.has_prompt("validate_placement")

    def test_get_variables(self) -> None:
        """Test extracting variables from a prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "vars.txt").write_text(
                "# Prompt: vars\n\n"
                "Hello {name}! Your {item} costs {price}."
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)
            variables = registry.get_variables("vars")

            assert "name" in variables
            assert "item" in variables
            assert "price" in variables
            assert len(variables) == 3

    def test_reload_single_prompt(self) -> None:
        """Test reloading a single prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            filepath = prompts_dir / "reload.txt"
            filepath.write_text("# Prompt: reload\n\nVersion 1")

            registry = PromptRegistry(prompts_dir=prompts_dir)
            assert registry.get_raw("reload") == "Version 1"

            # Modify the file
            filepath.write_text("# Prompt: reload\n\nVersion 2")

            # Still cached
            assert registry.get_raw("reload") == "Version 1"

            # Reload
            registry.reload("reload")
            assert registry.get_raw("reload") == "Version 2"

    def test_reload_all_prompts(self) -> None:
        """Test reloading all prompts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "a.txt").write_text("# Prompt: a\n\nA1")
            (prompts_dir / "b.txt").write_text("# Prompt: b\n\nB1")

            registry = PromptRegistry(prompts_dir=prompts_dir)
            assert registry.get_raw("a") == "A1"
            assert registry.get_raw("b") == "B1"

            # Modify files
            (prompts_dir / "a.txt").write_text("# Prompt: a\n\nA2")
            (prompts_dir / "b.txt").write_text("# Prompt: b\n\nB2")

            # Still cached
            assert registry.get_raw("a") == "A1"

            # Reload all
            registry.reload()
            assert registry.get_raw("a") == "A2"
            assert registry.get_raw("b") == "B2"

    def test_prompts_dir_property(self) -> None:
        """Test prompts_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            registry = PromptRegistry(prompts_dir=prompts_dir)
            assert registry.prompts_dir == prompts_dir

    def test_caching_prompts(self) -> None:
        """Test that prompts are cached after first load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "cached.txt").write_text("# Prompt: cached\n\nOriginal")

            registry = PromptRegistry(prompts_dir=prompts_dir)

            # First load
            result1 = registry.get_raw("cached")
            assert result1 == "Original"

            # Modify file
            (prompts_dir / "cached.txt").write_text("# Prompt: cached\n\nModified")

            # Should still be cached
            result2 = registry.get_raw("cached")
            assert result2 == "Original"

    def test_default_prompt_fallback(self) -> None:
        """Test falling back to default prompts when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)
            # Don't create any files

            registry = PromptRegistry(prompts_dir=prompts_dir)

            # Should still be able to get default prompts
            variables = registry.get_variables("classify_file")
            assert "filename" in variables
            assert "content" in variables
            assert "bins" in variables

    def test_parse_header_with_colon_in_description(self) -> None:
        """Test parsing header when description contains colons."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "colon.txt").write_text(
                "# Prompt: colon\n"
                "# Version: 1.0.0\n"
                "# Description: This: has: many: colons.\n"
                "\nContent"
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)
            metadata = registry.get_metadata("colon")
            assert metadata.description == "This: has: many: colons."

    def test_template_extraction_skips_all_header_comments(self) -> None:
        """Test that template extraction properly skips header comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            (prompts_dir / "header.txt").write_text(
                "# Prompt: header\n"
                "# Version: 1.0.0\n"
                "# Last-Modified: 2024-01-01\n"
                "# Description: Test.\n"
                "#\n"
                "# Additional comment\n"
                "\n"
                "Actual content starts here.\n"
                "More content."
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)
            template = registry.get_raw("header")

            assert not template.startswith("#")
            assert "Actual content starts here." in template
            assert "More content." in template


class TestDefaultPrompts:
    """Tests for the default prompt templates."""

    def test_default_prompts_exist(self) -> None:
        """Test that expected default prompts are defined."""
        expected_prompts = [
            "classify_file",
            "validate_placement",
            "suggest_subfolder",
            "detect_domain",
            "generate_rule",
            "assess_drift",
            "extract_metadata",
            "narrate_structure",
        ]
        for name in expected_prompts:
            assert name in DEFAULT_PROMPTS, f"Missing default prompt: {name}"

    def test_default_prompts_have_header(self) -> None:
        """Test that default prompts have proper headers."""
        for name, template in DEFAULT_PROMPTS.items():
            assert template.startswith("# Prompt:"), f"{name} missing Prompt header"
            assert "# Version:" in template, f"{name} missing Version header"
            assert "# Description:" in template, f"{name} missing Description header"

    def test_classify_file_prompt_variables(self) -> None:
        """Test classify_file prompt has expected variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            registry = PromptRegistry(prompts_dir=prompts_dir)
            variables = registry.get_variables("classify_file")

            assert "filename" in variables
            assert "content" in variables
            assert "bins" in variables

    def test_validate_placement_prompt_variables(self) -> None:
        """Test validate_placement prompt has expected variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            registry = PromptRegistry(prompts_dir=prompts_dir)
            variables = registry.get_variables("validate_placement")

            assert "filename" in variables
            assert "current_path" in variables
            assert "current_bin" in variables
            assert "expected_bin" in variables
            assert "content" in variables


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_prompt_function(self) -> None:
        """Test the get_prompt convenience function."""
        # This will use the default prompts directory
        # For testing, we need to ensure defaults exist
        result = get_prompt(
            "classify_file",
            filename="test.pdf",
            content="Test content",
            bins="Tax, Medical"
        )
        assert "test.pdf" in result
        assert "Test content" in result
        assert "Tax, Medical" in result

    def test_list_available_prompts_function(self) -> None:
        """Test the list_available_prompts convenience function."""
        prompts = list_available_prompts()
        assert "classify_file" in prompts
        assert "validate_placement" in prompts
        assert isinstance(prompts, list)


class TestPromptRegistryIntegration:
    """Integration tests for the prompt registry."""

    def test_full_workflow(self) -> None:
        """Test a complete workflow: create, load, substitute, reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"

            # Initialize registry (creates defaults)
            registry = PromptRegistry(prompts_dir=prompts_dir)

            # List prompts
            prompts = registry.list_prompts()
            assert len(prompts) > 0

            # Get a prompt with substitution
            result = registry.get(
                "classify_file",
                filename="invoice.pdf",
                content="Amount: $500",
                bins="Financial, Medical"
            )

            assert "invoice.pdf" in result
            assert "$500" in result
            assert "Financial, Medical" in result

            # Get metadata
            metadata = registry.get_metadata("classify_file")
            assert metadata.version == "1.0.0"

            # Check variables
            variables = registry.get_variables("classify_file")
            assert len(variables) == 3

    def test_custom_prompt_overrides_default(self) -> None:
        """Test that custom prompt files override defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)

            # Create a custom version of classify_file
            (prompts_dir / "classify_file.txt").write_text(
                "# Prompt: classify_file\n"
                "# Version: 2.0.0\n"
                "# Description: Custom classifier.\n"
                "\nCustom template for {filename}"
            )

            registry = PromptRegistry(prompts_dir=prompts_dir)

            # Should get the custom version
            result = registry.get("classify_file", filename="test.pdf")
            assert "Custom template for test.pdf" == result

            # Metadata should reflect custom version
            metadata = registry.get_metadata("classify_file")
            assert metadata.version == "2.0.0"
            assert metadata.description == "Custom classifier."

    def test_empty_directory_gets_defaults(self) -> None:
        """Test that an empty directory gets populated with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir(parents=True)
            # Directory exists but is empty

            _registry = PromptRegistry(prompts_dir=prompts_dir)

            # Default prompts should have been created
            assert (prompts_dir / "classify_file.txt").exists()
            assert (prompts_dir / "validate_placement.txt").exists()
