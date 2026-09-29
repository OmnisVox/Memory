"""Example using recovered field-benchmark calibrations.

These thresholds are *not* universal defaults. They came from the controlled
24-member vortex-family benchmark and are shown only as a reproducible configuration
example.
"""
import numpy as np

from adrianic_memory import (
    AddressableMemoryBank,
    SelectiveCommitController,
    ComparativeReplacementConfig,
)

scales = np.ones(12)
bank = AddressableMemoryBank(
    capacity=8,
    scales=scales,
    max_distance=0.20,
    min_margin=0.035,
)
commit = SelectiveCommitController(
    replacement_margin=0.28,
    replacement=ComparativeReplacementConfig(
        support_reference=3.0,
        retained_age_alpha=0.02,
    ),
)

print("Configured recovered field-benchmark policy:", bank.capacity, commit.replacement_margin)
