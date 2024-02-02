from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import torch
from comet import download_model, load_from_checkpoint

from . import MetricReferenceless, register


@register("comet_qe")
class MetricCOMETQE(MetricReferenceless):
    """COMET-QE metric class."""

    @dataclass
    class Config(MetricReferenceless.Config):
        """COMET-QE metric configuration.

        - model (str): Model name or path.
        - batch_size (int): Batch size.
        - float16 (bool): Use float16 for the forward computation.
        - cpu (bool): Use CPU for the forward computation.
        """

        model: str = "Unbabel/wmt22-cometkiwi-da"
        batch_size: int = 64
        float16: bool = False
        cpu: bool = False

    def __init__(self, cfg: MetricCOMETQE.Config):
        self.cfg = cfg
        self.scorer = load_from_checkpoint(download_model(cfg.model))
        self.scorer.eval()
        for param in self.scorer.parameters():
            param.requires_grad = False

        if not cfg.cpu and torch.cuda.is_available():
            self.scorer = self.scorer.cuda()
            if cfg.float16:
                self.scorer = self.scorer.half()

    @property
    def device(self) -> torch.device:
        """Returns the device of the model."""
        return self.scorer.device

    def score(self, hypothesis: str, source: str) -> float:
        """Calculate the score of the given hypothesis.

        Args:
            hypothesis (str): A hypothesis.
            source (str): A source.

        Returns:
            float: The score of the given hypothesis.
        """
        return self.scores([hypothesis], source).item()

    def scores(self, hypotheses: list[str], source: str) -> npt.NDArray[np.float32]:
        """Calculate the scores of hypotheses.

        Args:
            hypotheses (list[str]): Hypotheses.
            source (str): A source.

        Returns:
            NDArray[np.float32]: The scores of hypotheses.
        """
        data = [{"src": source, "mt": hyp} for hyp in hypotheses]
        model_output = self.scorer.predict(data, batch_size=self.cfg.batch_size, gpus=1)
        return np.array(model_output.scores).reshape(len(hypotheses))