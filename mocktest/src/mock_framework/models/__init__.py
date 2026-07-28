"""数据模型包"""

from .gherkin import Feature, Scenario, Step, ExamplesTable
from .arch import (
    ArchDoc,
    OpenAPISpec,
    DataFlow,
    DataFlowStep,
    StateMachine,
    StateTransition,
    NFR,
    ComponentSpec,
)
from .loader import TestCase, TechnicalMapping, Expectations
from .simulator import ExecutionTrace, TraceStep, SideEffect, StateTransitionRecord
from .validator import (
    ValidationResult,
    ValidationReport,
    DimensionResult,
    FailureAnalysis,
    WarningAnalysis,
    Recommendation,
)
from .gap import Gap, GapReport, GapLocation
from .modification import Modification, ModificationPlan
from .layer import Violation, ConsistencyReport

__all__ = [
    # Gherkin
    "Feature",
    "Scenario",
    "Step",
    "ExamplesTable",
    # Arch
    "ArchDoc",
    "OpenAPISpec",
    "DataFlow",
    "DataFlowStep",
    "StateMachine",
    "StateTransition",
    "NFR",
    "ComponentSpec",
    # Loader
    "TestCase",
    "TechnicalMapping",
    "Expectations",
    # Simulator
    "ExecutionTrace",
    "TraceStep",
    "SideEffect",
    "StateTransitionRecord",
    # Validator
    "ValidationResult",
    "ValidationReport",
    "DimensionResult",
    "FailureAnalysis",
    "WarningAnalysis",
    "Recommendation",
    # Gap
    "Gap",
    "GapReport",
    "GapLocation",
    # Modification
    "Modification",
    "ModificationPlan",
    # Layer
    "Violation",
    "ConsistencyReport",
]
