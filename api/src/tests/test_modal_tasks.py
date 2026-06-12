import json
import os
import pytest
from src.features.generation.modal_tasks import _load_graph_from_dict, run_generation


class TestLoadGraphFromDict:
    """Unit tests for graph validation helper."""

    def test_valid_graph_passes(self):
        """GIVEN a valid resolved graph dict
        WHEN validating it
        THEN it is returned unchanged.
        """
        graph = {"prompt": {"6": {"inputs": {"text": "test"}}}}
        result = _load_graph_from_dict(graph)
        assert result == graph

    def test_empty_graph_raises(self):
        """GIVEN an empty graph
        WHEN validating it
        THEN ValueError is raised.
        """
        with pytest.raises(ValueError):
            _load_graph_from_dict({})

    def test_missing_prompt_key_raises(self):
        """GIVEN a graph without 'prompt' key
        WHEN validating it
        THEN ValueError is raised.
        """
        with pytest.raises(ValueError):
            _load_graph_from_dict({"other": "data"})


class TestRunGeneration:
    """Unit tests for run_generation Modal function signature."""

    def test_run_generation_is_modal_function(self):
        """GIVEN the module is loaded
        THEN run_generation is a Modal function object.
        """
        import modal
        assert isinstance(run_generation, modal.Function)

    def test_run_generation_accepts_graph_param(self):
        """GIVEN the run_generation signature
        THEN it accepts job_id and graph parameters.
        """
        # Verify the function has the expected parameters by checking its local signature
        import inspect
        # Note: Modal wraps the function, so we inspect the underlying function
        sig = inspect.signature(run_generation.info.raw_f)
        params = list(sig.parameters.keys())
        assert "job_id" in params
        assert "graph" in params
