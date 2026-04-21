import pytest
from datetime import datetime, timedelta
from agents.schedule_engine import schedule_engine
from agents.status_classifier import status_classifier
from agents.forecast_agent import forecast_agent
from logic.lifecycle import lifecycle_manager

def test_chain_rule_drift_prevention():
    """
    Rule L01/L02: Chain Rule & Drift Prevention.
    Verifies that next_due_date is calculated from baseline, not completion.
    """
    baseline = "2024-01-01"
    interval = 180 # 6 months
    
    # Task 1: Due 2024-06-29 (180 days after 2024-01-01)
    # Task 2 should be scheduled from Task 1's DUE DATE as baseline.
    
    result = schedule_engine.calculate_next_task("Service", baseline, interval)
    
    # Next baseline should be 2024-06-29 (approx)
    expected_baseline = (datetime(2024, 1, 1) + timedelta(days=180)).strftime("%Y-%m-%d")
    assert result["next_baseline_start_date"] == expected_baseline
    
    # Next due should be 2024-12-26 (approx)
    expected_due = (datetime(2024, 1, 1) + timedelta(days=360)).strftime("%Y-%m-%d")
    assert result["next_due_date"] == expected_due

def test_status_classification_boundaries():
    """
    Rule L09: Status Classification.
    """
    today = datetime.now().date().strftime("%Y-%m-%d")
    overdue = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    critical = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    warning = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")
    upcoming = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    scheduled = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")
    
    assert status_classifier.classify_task(overdue)["status"] == "Overdue"
    assert status_classifier.classify_task(critical)["status"] == "Critical"
    assert status_classifier.classify_task(warning)["status"] == "Warning"
    assert status_classifier.classify_task(upcoming)["status"] == "Upcoming"
    assert status_classifier.classify_task(scheduled)["status"] == "Scheduled"

def test_forecast_formula_accuracy():
    """
    Rule L10: Forecast Formula.
    Demand = ((Capacity * 1.10) * Frequency) * Assets * 1.20 Buffer
    """
    capacity = 100
    frequency = 2
    assets = 10
    
    # Calculation:
    # ((100 * 1.1) * 2) * 10 * 1.2
    # (110 * 2) * 10 * 1.2
    # 220 * 10 * 1.2 = 2200 * 1.2 = 2640
    
    result = forecast_agent.calculate_fluid_demand(capacity, frequency, assets)
    assert result["quantity"] == 2640.0
    assert result["formula_breakdown"]["buffer"] == 1.20

def test_vintage_calculation():
    """
    Rule L08: Vintage Calculation.
    """
    # 10 years ago
    past_date = (datetime.now() - timedelta(days=365.25 * 10)).strftime("%Y-%m-%d")
    vintage = lifecycle_manager.calculate_vintage(past_date)
    assert 9.9 <= vintage <= 10.1 # Floating point tolerance
