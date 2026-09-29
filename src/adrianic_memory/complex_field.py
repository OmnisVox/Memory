from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class ComplexFieldConfig:
    dt: float = 0.01
    diffusion: float = 0.0
    tau_learning: float = 2.0
    recall_strength: float = 5.0


class ComplexMemoryField:
    """Reference implementation of the v3.1 complex memory primitive.

    The research patch defines:
        d chi/dt = D_chi Laplacian(chi) + L(t) * (psi - chi) / tau_chi
        d psi/dt|mem = R(t) * mu_chi * (chi - psi)

    This class implements that mechanism only. It does not claim benchmark equivalence
    with the historical field simulators.
    """

    def __init__(self, shape: tuple[int, ...], config: ComplexFieldConfig | None = None):
        self.config = config or ComplexFieldConfig()
        self.chi = np.zeros(shape, dtype=np.complex128)

    @staticmethod
    def _laplacian_periodic(x: np.ndarray) -> np.ndarray:
        if x.ndim != 2:
            return np.zeros_like(x)
        return (
            np.roll(x, 1, 0) + np.roll(x, -1, 0)
            + np.roll(x, 1, 1) + np.roll(x, -1, 1)
            - 4.0 * x
        )

    def learn(self, psi: np.ndarray, gate: float = 1.0) -> np.ndarray:
        psi = np.asarray(psi, dtype=np.complex128)
        if psi.shape != self.chi.shape:
            raise ValueError("psi shape must match memory field")
        c = self.config
        dchi = c.diffusion * self._laplacian_periodic(self.chi)
        dchi += float(gate) * (psi - self.chi) / c.tau_learning
        self.chi = self.chi + c.dt * dchi
        return self.chi.copy()

    def recall_delta(self, psi: np.ndarray, gate: float = 1.0) -> np.ndarray:
        psi = np.asarray(psi, dtype=np.complex128)
        if psi.shape != self.chi.shape:
            raise ValueError("psi shape must match memory field")
        return float(gate) * self.config.recall_strength * (self.chi - psi)

    def recall_step(self, psi: np.ndarray, gate: float = 1.0) -> np.ndarray:
        return np.asarray(psi, dtype=np.complex128) + self.config.dt * self.recall_delta(psi, gate)
