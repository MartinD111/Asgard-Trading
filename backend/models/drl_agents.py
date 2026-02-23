"""
DRL Agents — PPO and SAC stubs for Sharpe-ratio-maximising trading.
Full training requires stable-baselines3 + gymnasium + GPU.
"""
import logging
import numpy as np

logger = logging.getLogger(__name__)


class TradingEnvironment:
    """
    Custom Gymnasium environment for paper trading.
    State: [50 OHLCV candles × 5 features, position_flag, unrealized_pnl]
    Action space: {0: HOLD, 1: BUY, 2: SELL}
    Reward: Δ Sharpe Ratio per step
    """

    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity_curve = [initial_balance]
        self.position = 0  # 0=flat, 1=long, -1=short
        self.returns = []

    def step(self, action: int, price_change_pct: float):
        pnl = 0.0
        if self.position == 1 and price_change_pct:
            pnl = self.balance * 0.01 * price_change_pct
        elif self.position == -1 and price_change_pct:
            pnl = -self.balance * 0.01 * price_change_pct

        self.balance += pnl
        self.equity_curve.append(self.balance)
        self.returns.append(pnl / max(self.balance, 1))

        # Sharpe reward
        if len(self.returns) > 1:
            mean_r = np.mean(self.returns[-20:])
            std_r = np.std(self.returns[-20:]) + 1e-8
            reward = mean_r / std_r
        else:
            reward = 0.0

        if action == 1:
            self.position = 1
        elif action == 2:
            self.position = -1
        else:
            self.position = 0

        return reward

    def sharpe_ratio(self) -> float:
        if len(self.returns) < 2:
            return 0.0
        return float(np.mean(self.returns) / (np.std(self.returns) + 1e-8) * np.sqrt(252))


class PPOAgent:
    """
    PPO (Proximal Policy Optimization) agent stub.
    Production: train with stable_baselines3.PPO on TradingEnvironment.
    """

    def __init__(self):
        self.is_trained = False
        logger.info("PPOAgent initialised (stub)")

    def act(self, observation: np.ndarray) -> int:
        """Returns action: 0=HOLD, 1=BUY, 2=SELL."""
        if not self.is_trained:
            # Stub: random with slight buy bias
            return int(np.random.choice([0, 1, 2], p=[0.5, 0.3, 0.2]))
        # In production: return self.model.predict(observation)[0]
        return 0

    def train(self, env: TradingEnvironment, total_timesteps: int = 100_000):
        """
        Production training:
            from stable_baselines3 import PPO
            self.model = PPO("MlpPolicy", env, verbose=1)
            self.model.learn(total_timesteps=total_timesteps)
        """
        logger.info(f"PPOAgent.train() stub called with {total_timesteps} steps.")
        self.is_trained = True


class SACAgent:
    """
    SAC (Soft Actor-Critic) agent stub.
    Better suited for continuous action spaces (e.g., position sizing).
    Production: train with stable_baselines3.SAC.
    """

    def __init__(self):
        self.is_trained = False
        logger.info("SACAgent initialised (stub)")

    def act(self, observation: np.ndarray) -> float:
        """Returns continuous action in [-1, +1]: negative=short, positive=long, 0=hold."""
        if not self.is_trained:
            return float(np.random.uniform(-0.2, 0.2))
        return 0.0

    def train(self, env: TradingEnvironment, total_timesteps: int = 100_000):
        """
        Production training:
            from stable_baselines3 import SAC
            self.model = SAC("MlpPolicy", env, verbose=1)
            self.model.learn(total_timesteps=total_timesteps)
        """
        logger.info(f"SACAgent.train() stub called with {total_timesteps} steps.")
        self.is_trained = True
