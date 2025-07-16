from pathlib import Path
from typing import Dict
import pandas as pd
from abc import ABC, abstractmethod

from wasabi import msg

METRICS = ["token_acc", "morph_acc"]

class AbstractTrainer(ABC):
    """
    Abstract base class for all trainers, providing common setup functionality.

    Responsibilities:
    - Initialize common parameters
    - GPU and W&B setup
    - Define the `run` workflow
    """
    def __init__(
        self,
        lang: str,
        study: str,
        use_gpu: int = 0,
        log_to_wandb: bool = True,
        wandb_project: str = "trainer-project",
    ):
        self.lang = lang
        self.study = study
        self.use_gpu = use_gpu
        self.wandb_project = wandb_project
        self.wandb_run = None
        self.log_to_wandb = log_to_wandb
        self.data_dir = Path(__file__).resolve().parents[2] / 'data'
        self.models_dir = Path(__file__).resolve().parents[2] / 'models'

    def _setup_wandb(self) -> None:
        """Initialize Weights & Biases logging if enabled"""
        if not self.log_to_wandb:
            msg.info("W&B logging disabled.")
            return
        try:
            import wandb
            self.wandb_run = wandb.init(
                project=self.wandb_project,
                config={"lang": self.lang, "study": self.study, "use_gpu": True}
            )
            msg.info("Initialized Weights & Biases logging")
        except ImportError:
            msg.warning("wandb not installed; skipping W&B logging")
    
    @abstractmethod
    def training_step(self) -> Dict[str, float]:
        '''
        return metrics: Dict[str, float]
        This method should be implemented by concrete trainers to define the training logic.
        It should return a dictionary of metrics to log, such as accuracy or loss.
        Example:
        return {"loss": 0.123, "accuracy": 0.95}
        '''
        pass

    @abstractmethod
    def _setup_gpu(self) -> None:
        pass


    def train(self, data_df: pd.DataFrame) -> Dict[str, float]:
        """Concrete trainers must implement their training logic and return metrics."""
        """
        Execute the training workflow:
        - GPU setup
        - W&B setup
        - Delegate to `train`
        - Finalize W&B
        """
        self._setup_gpu()
        self._setup_wandb()
        metrics = self.training_step(data_df)
        if self.wandb_run:
            self.wandb_run.log(metrics)
            self.wandb_run.finish()
        return metrics
