"""Integration tests for the synthesis module."""

import pytest
from synthesis.coherence_checker import CoherenceChecker
from synthesis.contradiction_resolver import ContradictionResolver
from synthesis.final_renderer import FinalRenderer
from synthesis.formatting_engine import FormattingEngine
from synthesis.tone_controller import ToneController
from synthesis.response_merger import ResponseMerger


class TestSynthesisHappyPath:
    """Happy-path tests for the synthesis module."""

    def test_coherence_checker_validates_coherent_text(self):
        """Test that the coherence checker validates coherent text."""
        checker = CoherenceChecker()
        text = "The sky is blue. The sun is shining. It is a beautiful day."
        result = checker.check(text)
        assert result is not None
        assert result.is_coherent is True
        assert result.score >= 0.0
        assert result.score <= 1.0

    def test_contradiction_resolver_detects_no_contradictions(self):
        """Test that the contradiction resolver detects no contradictions in consistent text."""
        resolver = ContradictionResolver()
        text = "Water boils at 100 degrees Celsius. Ice melts at 0 degrees Celsius."
        result = resolver.resolve(text)
        assert result is not None
        assert len(result.contradictions) == 0

    def test_final_renderer_renders_response(self):
        """Test that the final renderer can render a response."""
        renderer = FinalRenderer()
        response_data = {
            "content": "This is a test response.",
            "metadata": {"source": "test"},
        }
        rendered = renderer.render(response_data)
        assert rendered is not None
        assert len(rendered) > 0

    def test_formatting_engine_formats_text(self):
        """Test that the formatting engine can format text."""
        engine = FormattingEngine()
        text = "test response"
        formatted = engine.format(text, format_type="plain")
        assert formatted is not None
        assert len(formatted) > 0

    def test_tone_controller_adjusts_tone(self):
        """Test that the tone controller can adjust the tone of text."""
        controller = ToneController()
        text = "The answer is 42."
        adjusted = controller.adjust_tone(text, tone="professional")
        assert adjusted is not None
        assert len(adjusted) > 0

    def test_response_merger_merges_responses(self):
        """Test that the response merger can merge multiple responses."""
        merger = ResponseMerger()
        responses = [
            {"content": "First part.", "source": "tool1"},
            {"content": "Second part.", "source": "tool2"},
        ]
        merged = merger.merge(responses)
        assert merged is not None
        assert "First part" in merged["content"] or "Second part" in merged["content"]


class TestSynthesisFailurePath:
    """Failure-path tests for the synthesis module."""

    def test_coherence_checker_handles_empty_input(self):
        """Test that the coherence checker handles empty input gracefully."""
        checker = CoherenceChecker()
        with pytest.raises(ValueError):
            checker.check("")

    def test_contradiction_resolver_handles_empty_input(self):
        """Test that the contradiction resolver handles empty input gracefully."""
        resolver = ContradictionResolver()
        with pytest.raises(ValueError):
            resolver.resolve("")

    def test_final_renderer_handles_empty_response(self):
        """Test that the final renderer handles empty response gracefully."""
        renderer = FinalRenderer()
        with pytest.raises(ValueError):
            renderer.render({})

    def test_formatting_engine_handles_invalid_format(self):
        """Test that the formatting engine handles invalid format type gracefully."""
        engine = FormattingEngine()
        with pytest.raises(ValueError):
            engine.format("test", format_type="invalid_format")

    def test_tone_controller_handles_invalid_tone(self):
        """Test that the tone controller handles invalid tone gracefully."""
        controller = ToneController()
        with pytest.raises(ValueError):
            controller.adjust_tone("test", tone="invalid_tone")

    def test_response_merger_handles_empty_responses(self):
        """Test that the response merger handles empty responses gracefully."""
        merger = ResponseMerger()
        with pytest.raises(ValueError):
            merger.merge([])


class TestSynthesisIntegration:
    """Integration tests for synthesis components working together."""

    def test_full_synthesis_pipeline(self):
        """Test the full synthesis pipeline from raw responses to final output."""
        # Step 1: Merge multiple responses
        merger = ResponseMerger()
        responses = [
            {"content": "The calculation result is 42.", "source": "calculator"},
            {"content": "The context is mathematics.", "source": "context"},
        ]
        merged = merger.merge(responses)
        assert merged is not None

        # Step 2: Check coherence
        checker = CoherenceChecker()
        coherence = checker.check(merged["content"])
        assert coherence is not None

        # Step 3: Resolve contradictions
        resolver = ContradictionResolver()
        resolved = resolver.resolve(merged["content"])
        assert resolved is not None

        # Step 4: Adjust tone
        controller = ToneController()
        toned = controller.adjust_tone(merged["content"], tone="professional")
        assert toned is not None

        # Step 5: Format
        engine = FormattingEngine()
        formatted = engine.format(toned, format_type="plain")
        assert formatted is not None

        # Step 6: Final render
        renderer = FinalRenderer()
        final = renderer.render({"content": formatted, "metadata": merged.get("metadata", {})})
        assert final is not None
        assert len(final) > 0

    def test_synthesis_with_contradiction_detection(self):
        """Test synthesis with contradiction detection and resolution."""
        merger = ResponseMerger()
        responses = [
            {"content": "The sky is blue.", "source": "source1"},
            {"content": "The sky is green.", "source": "source2"},
        ]
        merged = merger.merge(responses)

        resolver = ContradictionResolver()
        resolved = resolver.resolve(merged["content"])
        assert resolved is not None
        # Should detect the contradiction about sky color
        assert len(resolved.contradictions) > 0 or resolved.resolved_text != merged["content"]

    def test_synthesis_with_tone_adjustment(self):
        """Test synthesis with different tone adjustments."""
        text = "The answer is 42."
        controller = ToneController()

        professional = controller.adjust_tone(text, tone="professional")
        casual = controller.adjust_tone(text, tone="casual")
        formal = controller.adjust_tone(text, tone="formal")

        assert professional != casual or professional != formal
        assert all(len(t) > 0 for t in [professional, casual, formal])
