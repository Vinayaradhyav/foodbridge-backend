"""
AI Module 6: Logistics & Vehicle Route Optimization Engine
Exports:
- route_optimizer (RouteOptimizer instance)
- assignment_optimizer (AssignmentOptimizer instance)
"""

from app.ai.assignment.route_optimizer import route_optimizer, RouteOptimizer
from app.ai.assignment.optimizer import assignment_optimizer, AssignmentOptimizer

__all__ = [
    "route_optimizer",
    "RouteOptimizer",
    "assignment_optimizer",
    "AssignmentOptimizer"
]
