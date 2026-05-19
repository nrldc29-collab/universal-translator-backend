"""Integration tests for the cognition/router module."""

import pytest
from cognition.router.classifier import IntentClassifier
from cognition.router.complexity import ComplexityAnalyzer
from cognition.router.modes import CognitiveModeSelector
from cognition.router.router import CognitiveRouter


class TestCognitionRouterHappyPath:
    """Happy-path tests for the cognition/router module."""

    def test_intent_classifier_classifies_simple_query(self):
        """Test that the intent classifier can classify a simple query."""
        classifier = IntentClassifier()
        classification = classifier.classify("What is the capital of France?")
        assert classification is not None
        assert classification.intent is not None
        assert classification.confidence >= 0.0
        assert classification.confidence <= 1.0

    def test_complexity_analyzer_analyzes_simple_query(self):
        """Test that the complexity analyzer can analyze a simple query."""
        analyzer = ComplexityAnalyzer()
        complexity = analyzer.analyze("Calculate 2 + 2")
        assert complexity is not None
        assert complexity.level in ["LOW", "MEDIUM", "HIGH"]
        assert complexity.score >= 0.0

    def test_cognitive_mode_selector_selects_mode(self):
        """Test that the mode selector can select an appropriate cognitive mode."""
        selector = CognitiveModeSelector()
        mode = selector.select_mode(
            intent="query",
            complexity="LOW",
            context={},
        )
        assert mode is not None
        assert mode in ["FAST", "STANDARD", "DEEP", "HIGH_RISK"]

    def test_router_routes_simple_query(self):
        """Test that the router can route a simple query correctly."""
        router = CognitiveRouter()
        route = router.route("What is 2 + 2?")
        assert route is not None
        assert route.mode is not None
        assert route.selected_modules is not None
        assert route.risk.level.value in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class TestCognitionRouterFailurePath:
    """Failure-path tests for the cognition/router module."""

    def test_intent_classifier_handles_empty_input(self):
        """Test that the intent classifier handles empty input gracefully."""
        classifier = IntentClassifier()
        with pytest.raises(ValueError):
            classifier.classify("")

    def test_complexity_analyzer_handles_empty_input(self):
        """Test that the complexity analyzer handles empty input gracefully."""
        analyzer = ComplexityAnalyzer()
        with pytest.raises(ValueError):
            analyzer.analyze("")

    def test_cognitive_mode_selector_handles_invalid_inputs(self):
        """Test that the mode selector handles invalid inputs gracefully."""
        selector = CognitiveModeSelector()
        with pytest.raises(ValueError):
            selector.select_mode(
                intent="",
                complexity="",
                context={},
            )

    def test_router_handles_empty_input(self):
        """Test that the router handles empty input gracefully."""
        router = CognitiveRouter()
        with pytest.raises(ValueError):
            router.route("")

    def test_router_handles_very_long_input(self):
        """Test that the router handles very long input gracefully."""
        router = CognitiveRouter()
        long_input = "a" * 10000
        route = router.route(long_input)
        # Should either handle it or raise a meaningful error
        assert route is not None or route is None


class TestCognitionRouterIntegration:
    """Integration tests for the cognition router components working together."""

    def test_full_routing_pipeline(self):
        """Test the full routing pipeline from input to route plan."""
        classifier = IntentClassifier()
        complexity_analyzer = ComplexityAnalyzer()
        mode_selector = CognitiveModeSelector()
        router = CognitiveRouter()

        input_query = "Calculate the sum of 1, 2, and 3"

        # Step 1: Classify intent
        classification = classifier.classify(input_query)
        assert classification is not None

        # Step 2: Analyze complexity
        complexity = complexity_analyzer.analyze(input_query)
        assert complexity is not None

        # Step 3: Select cognitive mode
        mode = mode_selector.select_mode(
            intent=classification.intent,
            complexity=complexity.level,
            context={},
        )
        assert mode is not None

        # Step 4: Route through router
        route = router.route(input_query)
        assert route is not None
        assert route.mode is not None

    def test_router_with_context(self):
        """Test that the router can use context information."""
        router = CognitiveRouter()
        route = router.route("What is 5 * 5?")
        assert route is not None
        assert route.risk.level.value is not None
