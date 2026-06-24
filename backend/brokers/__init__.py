"""Broker execution package — abstract interface + implementations."""
from brokers.base import ExecutionBroker, OrderResult
from brokers.paper import PaperBroker

__all__ = ["ExecutionBroker", "OrderResult", "PaperBroker"]
