"""Training policies with a specifiable reward function and collect trajectories."""
from typing import List, Union

from stable_baselines3.common import base_class, vec_env

from imitation.data import types, wrappers
from imitation.rewards import common as rewards_common
from imitation.rewards import reward_nets
from imitation.util import reward_wrapper


class AgentTrainer:
    """Wrapper for training an SB3 algorithm on an arbitrary reward function.

    TODO(ejnnr): For preference comparisons, we might want to allow something more
    general at some point; only the .train() method is required. Also not clear yet
    how we want to deal with sampling/training: they should probably be separate
    (if only because we need rendering when sampling and using human feedback,
    but not when training), but on the other hand, sampling in addition to training
    can be unnecessary overhead.
    """

    def __init__(
        self,
        algorithm: base_class.BaseAlgorithm,
        reward_fn: Union[rewards_common.RewardFn, reward_nets.RewardNet],
    ):
        """Initialize the agent trainer.

        Args:
            algorithm: the stable-baselines algorithm to use for training.
                Its environment must be set.
            reward_fn: either a RewardFn or a RewardNet instance that will supply
                the rewards used for training the agent.
        """
        self.algorithm = algorithm
        if isinstance(reward_fn, reward_nets.RewardNet):
            reward_fn = reward_fn.predict
        self.reward_fn = reward_fn

        venv = self.algorithm.get_env()
        if not isinstance(venv, vec_env.VecEnv):
            raise ValueError("The environment for the agent algorithm must be set.")
        # The BufferingWrapper records all trajectories, so we can return
        # them after training. This should come first (before the wrapper that
        # changes the reward function), so that we return the original environment
        # rewards.
        self.buffering_wrapper = wrappers.BufferingWrapper(venv)
        self.venv = reward_wrapper.RewardVecEnvWrapper(
            self.buffering_wrapper, reward_fn
        )
        self.algorithm.set_env(self.venv)

    def train(self, total_timesteps: int, **kwargs) -> List[types.TrajectoryWithRew]:
        """Train the agent using the reward function specified during instantiation.

        Args:
            total_timesteps: number of environment timesteps to train for
            **kwargs: other keyword arguments to pass to BaseAlgorithm.train()

        Returns:
            a list of all trajectories that occurred during training, including their
            original environment rewards (rather than the ones computed using reward_fn)
        """
        # to clear the trajectory buffer
        self.venv.reset()
        self.algorithm.learn(total_timesteps=total_timesteps, **kwargs)
        return self._pop_trajectories()

    @property
    def policy(self):
        return self.algorithm.policy

    def _pop_trajectories(self) -> List[types.TrajectoryWithRew]:
        return self.buffering_wrapper.pop_trajectories()
