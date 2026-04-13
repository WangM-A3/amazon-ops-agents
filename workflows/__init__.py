"""
Workflows Module - 预置工作流
"""

from .presets import (
    PresetWorkflow,
    WorkflowStep,
    WorkflowEngine,
    WorkflowExecutionResult,
    WorkflowStatus,
    PRESET_WORKFLOWS,
    WORKFLOW_ENGINE,
    # 四个预置工作流
    WORKFLOW_NEW_PRODUCT_LAUNCH,
    WORKFLOW_AD_OPTIMIZATION,
    WORKFLOW_INVENTORY_ALERT,
    WORKFLOW_CUSTOMER_SERVICE,
)

__all__ = [
    "PresetWorkflow",
    "WorkflowStep",
    "WorkflowEngine",
    "WorkflowExecutionResult",
    "WorkflowStatus",
    "PRESET_WORKFLOWS",
    "WORKFLOW_ENGINE",
    "WORKFLOW_NEW_PRODUCT_LAUNCH",
    "WORKFLOW_AD_OPTIMIZATION",
    "WORKFLOW_INVENTORY_ALERT",
    "WORKFLOW_CUSTOMER_SERVICE",
]
