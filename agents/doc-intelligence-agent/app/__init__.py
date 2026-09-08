"""doc-intelligence-agent package."""

from google.adk.workflow import FunctionNode

# Ensure FunctionNode instances are directly callable as functions across the application
if "__call__" not in FunctionNode.__dict__:
    def _function_node_call(self, *args, **kwargs):
        func = getattr(self, "_func", None)
        if callable(func):
            return func(*args, **kwargs)
        raise TypeError(f"FunctionNode '{self.name}' has no underlying callable function.")

    FunctionNode.__call__ = _function_node_call
