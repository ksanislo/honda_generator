"""Tests for Honda Generator coordinator logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.honda_generator.api import Device, DeviceType
from custom_components.honda_generator.coordinator import HondaGeneratorCoordinator
from custom_components.honda_generator.services import ServiceType


@pytest.fixture
def coordinator(mock_config_entry: MagicMock) -> HondaGeneratorCoordinator:
    """Create a coordinator instance for testing."""
    mock_hass = MagicMock()

    def _close_coroutine(coro):
        """Close coroutines to prevent 'was never awaited' warnings."""
        if hasattr(coro, "close"):
            coro.close()

    mock_hass.async_create_task = _close_coroutine

    coord = HondaGeneratorCoordinator(mock_hass, mock_config_entry)
    coord.hass = mock_hass
    # Make store async-compatible
    coord._store = MagicMock()
    coord._store.async_save = AsyncMock()
    coord._store.async_load = AsyncMock(return_value=None)
    return coord


def _make_history(entries: list[tuple[int, datetime]]) -> list[dict]:
    """Create runtime_history from (hours, datetime) tuples."""
    return [{"hours": h, "ts": ts.isoformat()} for h, ts in entries]


# ---------------------------------------------------------------------------
# get_hours_per_day
# ---------------------------------------------------------------------------


class TestGetHoursPerDay:
    """Test usage rate calculation."""

    def test_empty_history(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._runtime_history = []
        assert coordinator.get_hours_per_day() is None

    def test_single_entry(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._runtime_history = _make_history(
            [
                (100, datetime(2026, 2, 15, 10, 0)),
            ]
        )
        assert coordinator.get_hours_per_day() is None

    def test_two_entries(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._runtime_history = _make_history(
            [
                (100, datetime(2026, 2, 15, 10, 0)),
                (112, datetime(2026, 2, 16, 10, 0)),
            ]
        )
        assert coordinator.get_hours_per_day() == pytest.approx(12.0)

    def test_steady_usage_over_days(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        base = datetime(2026, 2, 14, 8, 0)
        coordinator._runtime_history = _make_history(
            [
                (100, base),
                (104, base + timedelta(days=1)),
                (108, base + timedelta(days=2)),
                (112, base + timedelta(days=3)),
            ]
        )
        assert coordinator.get_hours_per_day() == pytest.approx(4.0)

    def test_overnight_idle_included(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Overnight idle should NOT be excluded (it's normal usage)."""
        entries = [
            (100, datetime(2026, 2, 15, 8, 0)),
            (101, datetime(2026, 2, 15, 9, 0)),
            (102, datetime(2026, 2, 15, 10, 0)),
            (103, datetime(2026, 2, 15, 11, 0)),
            (104, datetime(2026, 2, 15, 12, 0)),
            # 20h overnight gap
            (105, datetime(2026, 2, 16, 8, 0)),
            (106, datetime(2026, 2, 16, 9, 0)),
            (107, datetime(2026, 2, 16, 10, 0)),
            (108, datetime(2026, 2, 16, 11, 0)),
        ]
        coordinator._runtime_history = _make_history(entries)
        rate = coordinator.get_hours_per_day()
        # 8h over 27 wall-clock hours (1.125 days) = 7.11 h/day
        assert rate == pytest.approx(8.0 / (27.0 / 24.0), rel=0.01)

    def test_seven_day_gap_detected(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Entries >7 days apart → discard pre-gap data."""
        coordinator._runtime_history = _make_history(
            [
                (90, datetime(2026, 1, 1, 10, 0)),
                (95, datetime(2026, 1, 3, 10, 0)),
                # 9-day gap
                (96, datetime(2026, 1, 12, 10, 0)),
                (100, datetime(2026, 1, 14, 10, 0)),
            ]
        )
        # Only post-gap: 4h over 2 days
        assert coordinator.get_hours_per_day() == pytest.approx(2.0)

    def test_gap_exactly_seven_days(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._runtime_history = _make_history(
            [
                (90, datetime(2026, 2, 1, 10, 0)),
                (95, datetime(2026, 2, 3, 10, 0)),
                # Exactly 7 days
                (96, datetime(2026, 2, 10, 10, 0)),
                (100, datetime(2026, 2, 12, 10, 0)),
            ]
        )
        assert coordinator.get_hours_per_day() == pytest.approx(2.0)

    def test_gap_under_seven_days_included(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._runtime_history = _make_history(
            [
                (100, datetime(2026, 2, 10, 10, 0)),
                (104, datetime(2026, 2, 12, 10, 0)),
                # 5-day gap (below threshold)
                (105, datetime(2026, 2, 17, 10, 0)),
                (108, datetime(2026, 2, 18, 10, 0)),
            ]
        )
        # All data: 8h over 8 days
        assert coordinator.get_hours_per_day() == pytest.approx(1.0)

    def test_multiple_gaps_uses_last(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._runtime_history = _make_history(
            [
                (80, datetime(2025, 12, 1, 10, 0)),
                (85, datetime(2025, 12, 3, 10, 0)),
                # 9-day gap
                (86, datetime(2025, 12, 12, 10, 0)),
                (90, datetime(2025, 12, 14, 10, 0)),
                # 11-day gap
                (91, datetime(2025, 12, 25, 10, 0)),
                (95, datetime(2025, 12, 27, 10, 0)),
            ]
        )
        # Only data after LAST gap: 4h over 2 days
        assert coordinator.get_hours_per_day() == pytest.approx(2.0)

    def test_only_one_entry_after_gap(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._runtime_history = _make_history(
            [
                (90, datetime(2026, 1, 1, 10, 0)),
                (95, datetime(2026, 1, 3, 10, 0)),
                # 10-day gap, then only 1 entry
                (96, datetime(2026, 1, 14, 10, 0)),
            ]
        )
        assert coordinator.get_hours_per_day() is None

    def test_zero_elapsed_time(self, coordinator: HondaGeneratorCoordinator) -> None:
        ts = datetime(2026, 2, 15, 10, 0)
        coordinator._runtime_history = _make_history(
            [
                (100, ts),
                (101, ts),
            ]
        )
        assert coordinator.get_hours_per_day() is None

    def test_unsorted_entries(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._runtime_history = _make_history(
            [
                (108, datetime(2026, 2, 16, 10, 0)),
                (100, datetime(2026, 2, 14, 10, 0)),
                (104, datetime(2026, 2, 15, 10, 0)),
            ]
        )
        # 8h over 2 days
        assert coordinator.get_hours_per_day() == pytest.approx(4.0)

    def test_malformed_entries_skipped(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._runtime_history = [
            {"hours": 100, "ts": "2026-02-15T10:00:00"},
            {"bad_key": 101},
            {"hours": 102, "ts": "not-a-date"},
            {"hours": 104, "ts": "2026-02-16T10:00:00"},
        ]
        # Only entries 0 and 3 are valid: 4h over 1 day
        assert coordinator.get_hours_per_day() == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# _validate_runtime_hours
# ---------------------------------------------------------------------------


class TestValidateRuntimeHours:
    """Test runtime hours plausibility validation."""

    def test_no_stored_value(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = None
        assert coordinator._validate_runtime_hours(100, datetime.now()) is True

    def test_not_an_increase(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = datetime.now()
        assert coordinator._validate_runtime_hours(100, datetime.now()) is True
        assert coordinator._validate_runtime_hours(99, datetime.now()) is True

    def test_no_stored_timestamp(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = None
        assert coordinator._validate_runtime_hours(110, datetime.now()) is True

    def test_plausible_increase(self, coordinator: HondaGeneratorCoordinator) -> None:
        now = datetime.now()
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = now - timedelta(hours=5)
        assert coordinator._validate_runtime_hours(103, now) is True

    def test_at_max_boundary(self, coordinator: HondaGeneratorCoordinator) -> None:
        """Increase = elapsed + 1 hour → valid (rounding allowance)."""
        now = datetime.now()
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = now - timedelta(hours=5)
        # max_increase = 5 + 1 = 6
        assert coordinator._validate_runtime_hours(106, now) is True

    def test_implausible_forward_jump(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        now = datetime.now()
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = now - timedelta(hours=2)
        # max_increase = 2 + 1 = 3, but delta is 10
        assert coordinator._validate_runtime_hours(110, now) is False

    def test_rounding_allowance(self, coordinator: HondaGeneratorCoordinator) -> None:
        now = datetime.now()
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = now - timedelta(minutes=30)
        # max_increase = 0.5 + 1 = 1.5 → 1 ok, 2 not
        assert coordinator._validate_runtime_hours(101, now) is True
        assert coordinator._validate_runtime_hours(102, now) is False


# ---------------------------------------------------------------------------
# _apply_runtime_hours_bounds
# ---------------------------------------------------------------------------


class TestApplyRuntimeHoursBounds:
    """Test device state correction for runtime hours."""

    @staticmethod
    def _runtime_device(hours: int) -> list[Device]:
        return [
            Device(
                device_id=1,
                device_unique_id="test_runtime",
                device_type=DeviceType.RUNTIME_HOURS,
                name="Runtime Hours",
                state=hours,
            )
        ]

    def test_no_stored_value(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = None
        devices = self._runtime_device(100)
        coordinator._apply_runtime_hours_bounds(devices)
        assert devices[0].state == 100

    def test_valid_increase(self, coordinator: HondaGeneratorCoordinator) -> None:
        now = datetime.now()
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = now - timedelta(hours=5)
        devices = self._runtime_device(103)
        coordinator._apply_runtime_hours_bounds(devices)
        assert devices[0].state == 103

    def test_backwards_jump_corrected(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = datetime.now()
        devices = self._runtime_device(95)
        coordinator._apply_runtime_hours_bounds(devices)
        assert devices[0].state == 100

    def test_implausible_forward_jump_corrected(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        now = datetime.now()
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = now - timedelta(hours=1)
        devices = self._runtime_device(200)
        coordinator._apply_runtime_hours_bounds(devices)
        assert devices[0].state == 100

    def test_none_state_skipped(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 100
        devices = [
            Device(
                device_id=1,
                device_unique_id="test",
                device_type=DeviceType.RUNTIME_HOURS,
                name="Runtime Hours",
                state=None,
            )
        ]
        coordinator._apply_runtime_hours_bounds(devices)
        assert devices[0].state is None

    def test_non_runtime_device_unchanged(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._stored_runtime_hours = 100
        devices = [
            Device(
                device_id=1,
                device_unique_id="test_current",
                device_type=DeviceType.CURRENT,
                name="Current",
                state=5.5,
            )
        ]
        coordinator._apply_runtime_hours_bounds(devices)
        assert devices[0].state == 5.5


# ---------------------------------------------------------------------------
# is_service_due
# ---------------------------------------------------------------------------


class TestIsServiceDue:
    """Test service due checks."""

    def test_no_record(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 200
        coordinator._service_records = {}
        assert coordinator.is_service_due(ServiceType.OIL_CHANGE) is False

    def test_hours_not_reached(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 150
        coordinator._service_records = {
            "oil_change": {"hours": 100, "date": "2026-01-01T00:00:00"}
        }
        # 50h since service, interval 100h → not due
        assert coordinator.is_service_due(ServiceType.OIL_CHANGE) is False

    def test_hours_reached(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 200
        coordinator._service_records = {
            "oil_change": {"hours": 100, "date": "2026-01-01T00:00:00"}
        }
        # 100h since service, interval 100h → due
        assert coordinator.is_service_due(ServiceType.OIL_CHANGE) is True

    def test_days_reached(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 110
        old_date = (datetime.now() - timedelta(days=200)).isoformat()
        coordinator._service_records = {"oil_change": {"hours": 100, "date": old_date}}
        # Only 10h (under 100h), but 200 days > 180 → due by calendar
        assert coordinator.is_service_due(ServiceType.OIL_CHANGE) is True

    def test_neither_reached(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 120
        recent_date = (datetime.now() - timedelta(days=30)).isoformat()
        coordinator._service_records = {
            "oil_change": {"hours": 100, "date": recent_date}
        }
        assert coordinator.is_service_due(ServiceType.OIL_CHANGE) is False

    def test_breakin_oil_change_new_engine(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Break-in interval (20h) applies when last service < 20h."""
        coordinator._stored_runtime_hours = 20
        coordinator._service_records = {
            "oil_change": {"hours": 0, "date": datetime.now().isoformat()}
        }
        # 20h since service, break-in interval is 20h → due
        assert coordinator.is_service_due(ServiceType.OIL_CHANGE) is True

    def test_breakin_not_applied_after_first_service(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._stored_runtime_hours = 40
        coordinator._service_records = {
            "oil_change": {"hours": 20, "date": datetime.now().isoformat()}
        }
        # last_service_hours=20 (>= 20), standard interval 100h applies
        # 20h since service < 100h → not due
        assert coordinator.is_service_due(ServiceType.OIL_CHANGE) is False

    def test_service_not_for_model(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """EU2200i doesn't have timing belt service."""
        coordinator._stored_runtime_hours = 999
        coordinator._service_records = {
            "timing_belt": {"hours": 0, "date": "2020-01-01T00:00:00"}
        }
        assert coordinator.is_service_due(ServiceType.TIMING_BELT) is False

    def test_no_stored_runtime(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = None
        coordinator._service_records = {
            "oil_change": {"hours": 0, "date": datetime.now().isoformat()}
        }
        # current_hours defaults to 0, 0 - 0 = 0 < 20 (break-in) → not due
        assert coordinator.is_service_due(ServiceType.OIL_CHANGE) is False

    def test_hours_only_service(self, coordinator: HondaGeneratorCoordinator) -> None:
        """EU2200i combustion_chamber: hours=300, days=None."""
        coordinator._stored_runtime_hours = 400
        coordinator._service_records = {
            "combustion_chamber": {"hours": 0, "date": datetime.now().isoformat()}
        }
        assert coordinator.is_service_due(ServiceType.COMBUSTION_CHAMBER) is True

    def test_days_only_service(self, coordinator: HondaGeneratorCoordinator) -> None:
        """EU2200i fuel_system_check: hours=None, days=730."""
        coordinator._stored_runtime_hours = 50
        old_date = (datetime.now() - timedelta(days=800)).isoformat()
        coordinator._service_records = {
            "fuel_system_check": {"hours": 50, "date": old_date}
        }
        assert coordinator.is_service_due(ServiceType.FUEL_SYSTEM_CHECK) is True


# ---------------------------------------------------------------------------
# get_estimated_service_date
# ---------------------------------------------------------------------------


class TestGetEstimatedServiceDate:
    """Test service date estimation."""

    def test_no_record(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._service_records = {}
        coordinator._stored_runtime_hours = 100
        assert coordinator.get_estimated_service_date(ServiceType.OIL_CHANGE) is None

    def test_service_not_for_model(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        assert coordinator.get_estimated_service_date(ServiceType.TIMING_BELT) is None

    def test_hours_based_estimate(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 150
        coordinator._service_records = {
            "oil_change": {"hours": 100, "date": datetime.now().isoformat()}
        }
        coordinator._service_due_dates = {}
        # Rate = 5 h/day (25h over 5 days) — must stay under 7-day gap threshold
        base = datetime(2026, 2, 12, 8, 0)
        coordinator._runtime_history = _make_history(
            [
                (125, base),
                (150, base + timedelta(days=5)),
            ]
        )
        result = coordinator.get_estimated_service_date(ServiceType.OIL_CHANGE)
        assert result is not None
        # hours_remaining = 100 + 100 - 150 = 50h, at 5 h/day → 10 days out
        days_until = (result - datetime.now(tz=timezone.utc)).total_seconds() / 86400
        assert 9 < days_until < 11

    def test_calendar_based_estimate(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Falls back to calendar interval when no rate data."""
        coordinator._stored_runtime_hours = 100
        service_date = datetime.now() - timedelta(days=90)
        coordinator._service_records = {
            "oil_change": {"hours": 100, "date": service_date.isoformat()}
        }
        coordinator._runtime_history = []
        coordinator._service_due_dates = {}
        result = coordinator.get_estimated_service_date(ServiceType.OIL_CHANGE)
        assert result is not None
        # Calendar: service_date + 180 days → ~90 days from now
        days_until = (result - datetime.now(tz=timezone.utc)).total_seconds() / 86400
        assert 88 < days_until < 92

    def test_returns_earlier_estimate(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """When both estimates exist, return the earlier one."""
        coordinator._stored_runtime_hours = 195
        service_date = datetime.now() - timedelta(days=10)
        coordinator._service_records = {
            "oil_change": {"hours": 100, "date": service_date.isoformat()}
        }
        coordinator._service_due_dates = {}
        # Rate ≈ 19 h/day (95h over 5 days) → hours_remaining = 5h → ~0.26 days
        base = datetime(2026, 2, 12, 8, 0)
        coordinator._runtime_history = _make_history(
            [
                (100, base),
                (195, base + timedelta(days=5)),
            ]
        )
        result = coordinator.get_estimated_service_date(ServiceType.OIL_CHANGE)
        assert result is not None
        # Hours estimate (~0.26 days) should win over calendar (~170 days)
        days_until = (result - datetime.now(tz=timezone.utc)).total_seconds() / 86400
        assert days_until < 2

    def test_breakin_interval_for_new_engine(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._stored_runtime_hours = 10
        coordinator._service_records = {
            "oil_change": {"hours": 0, "date": datetime.now().isoformat()}
        }
        coordinator._service_due_dates = {}
        # Rate = 5 h/day → remaining = 20 - 10 = 10h → 2 days
        base = datetime(2026, 2, 10, 8, 0)
        coordinator._runtime_history = _make_history(
            [
                (0, base),
                (10, base + timedelta(days=2)),
            ]
        )
        result = coordinator.get_estimated_service_date(ServiceType.OIL_CHANGE)
        assert result is not None
        days_until = (result - datetime.now(tz=timezone.utc)).total_seconds() / 86400
        assert 1 < days_until < 3

    def test_overdue_snapshot_persisted(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Once overdue, snapshot locks the estimated date."""
        coordinator._stored_runtime_hours = 250
        old_date = (datetime.now() - timedelta(days=200)).isoformat()
        coordinator._service_records = {"oil_change": {"hours": 100, "date": old_date}}
        coordinator._service_due_dates = {}
        base = datetime(2026, 2, 1, 8, 0)
        coordinator._runtime_history = _make_history(
            [
                (200, base),
                (250, base + timedelta(days=5)),
            ]
        )
        result1 = coordinator.get_estimated_service_date(ServiceType.OIL_CHANGE)
        assert "oil_change" in coordinator._service_due_dates
        result2 = coordinator.get_estimated_service_date(ServiceType.OIL_CHANGE)
        assert result1 == result2

    def test_snapshot_cleared_when_not_due(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._stored_runtime_hours = 150
        recent_date = datetime.now().isoformat()
        coordinator._service_records = {
            "oil_change": {"hours": 100, "date": recent_date}
        }
        coordinator._service_due_dates = {"oil_change": "2026-01-01T00:00:00+00:00"}
        base = datetime(2026, 2, 10, 8, 0)
        coordinator._runtime_history = _make_history(
            [
                (100, base),
                (150, base + timedelta(days=10)),
            ]
        )
        coordinator.get_estimated_service_date(ServiceType.OIL_CHANGE)
        assert "oil_change" not in coordinator._service_due_dates


# ---------------------------------------------------------------------------
# _async_save_runtime_hours
# ---------------------------------------------------------------------------


class TestSaveRuntimeHours:
    """Test runtime hours persistence."""

    @pytest.mark.asyncio
    async def test_saves_increase(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = datetime.now() - timedelta(
            hours=2
        )
        coordinator._runtime_history = []
        coordinator._services_initialized = True

        await coordinator._async_save_runtime_hours(102)

        assert coordinator._stored_runtime_hours == 102
        assert len(coordinator._runtime_history) == 1
        assert coordinator._runtime_history[0]["hours"] == 102
        coordinator._store.async_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_equal_value(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = datetime.now()
        coordinator._runtime_history = []
        coordinator._services_initialized = True

        await coordinator._async_save_runtime_hours(100)

        assert coordinator._stored_runtime_hours == 100
        assert len(coordinator._runtime_history) == 0
        coordinator._store.async_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_decrease(self, coordinator: HondaGeneratorCoordinator) -> None:
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = datetime.now()
        coordinator._runtime_history = []
        coordinator._services_initialized = True

        await coordinator._async_save_runtime_hours(95)

        assert coordinator._stored_runtime_hours == 100
        coordinator._store.async_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_implausible(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        now = datetime.now()
        coordinator._stored_runtime_hours = 100
        coordinator._stored_runtime_hours_timestamp = now - timedelta(hours=1)
        coordinator._runtime_history = []
        coordinator._services_initialized = True

        await coordinator._async_save_runtime_hours(200)

        assert coordinator._stored_runtime_hours == 100
        coordinator._store.async_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_prunes_old_history(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """History entries outside the 24h runtime window are pruned."""
        coordinator._stored_runtime_hours = 120
        coordinator._stored_runtime_hours_timestamp = datetime.now() - timedelta(
            hours=6
        )
        coordinator._services_initialized = True
        coordinator._runtime_history = [
            {"hours": 90, "ts": "2026-02-10T10:00:00"},  # 90 < 125-24=101 → pruned
            {"hours": 100, "ts": "2026-02-12T10:00:00"},  # 100 < 101 → pruned
            {"hours": 110, "ts": "2026-02-14T10:00:00"},  # 110 >= 101 → kept
            {"hours": 120, "ts": "2026-02-16T10:00:00"},  # 120 >= 101 → kept
        ]

        await coordinator._async_save_runtime_hours(125)

        hours = [e["hours"] for e in coordinator._runtime_history]
        assert 90 not in hours
        assert 100 not in hours
        assert 110 in hours
        assert 120 in hours
        assert 125 in hours

    @pytest.mark.asyncio
    async def test_first_time_initializes_services(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """First runtime hours reading triggers service record initialization."""
        coordinator._stored_runtime_hours = None
        coordinator._service_records = {}
        coordinator._runtime_history = []

        await coordinator._async_save_runtime_hours(50)

        assert coordinator._stored_runtime_hours == 50
        # EU2200i has 9 services, all should be initialized
        assert len(coordinator._service_records) > 0
        # Oil change on engine with 50h (> 20h break-in) → initialized at 50
        assert coordinator._service_records["oil_change"]["hours"] == 50

    @pytest.mark.asyncio
    async def test_first_time_breakin_oil_at_zero(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """New engine (< 20h) gets oil change initialized at 0 for break-in."""
        coordinator._stored_runtime_hours = None
        coordinator._service_records = {}
        coordinator._runtime_history = []

        await coordinator._async_save_runtime_hours(10)

        assert coordinator._service_records["oil_change"]["hours"] == 0

    @pytest.mark.asyncio
    async def test_upgrade_initializes_missing_services(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Upgrade path: stored runtime hours exist but some services lack records."""
        # Simulate pre-upgrade state: runtime hours stored, only oil_change tracked
        coordinator._stored_runtime_hours = 2413
        coordinator._service_records = {
            "oil_change": {"hours": 2300, "date": "2025-10-17T12:00:00"}
        }
        coordinator._runtime_history = []
        coordinator._services_initialized = False

        # Runtime hours unchanged, but first call this session
        await coordinator._async_save_runtime_hours(2413)

        # Oil change record should be untouched (already existed)
        assert coordinator._service_records["oil_change"]["hours"] == 2300
        # Other services should now be initialized
        assert len(coordinator._service_records) > 1
        assert "spark_plug_check" in coordinator._service_records
        assert coordinator._service_records["spark_plug_check"]["hours"] == 2413

    @pytest.mark.asyncio
    async def test_services_initialized_only_once_per_session(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        """Service initialization only runs once per coordinator lifecycle."""
        coordinator._stored_runtime_hours = None
        coordinator._service_records = {}
        coordinator._runtime_history = []

        await coordinator._async_save_runtime_hours(50)
        assert len(coordinator._service_records) > 0
        assert coordinator._services_initialized is True

        # Clear records and save again — should NOT re-initialize
        coordinator._service_records = {}
        await coordinator._async_save_runtime_hours(51)
        assert len(coordinator._service_records) == 0


# ---------------------------------------------------------------------------
# async_mark_service_complete
# ---------------------------------------------------------------------------


class TestMarkServiceComplete:
    """Test marking a service as complete."""

    @pytest.mark.asyncio
    async def test_records_service(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._stored_runtime_hours = 200
        coordinator._service_records = {}
        coordinator._service_due_dates = {}

        await coordinator.async_mark_service_complete(ServiceType.OIL_CHANGE)

        record = coordinator._service_records["oil_change"]
        assert record["hours"] == 200
        assert "date" in record
        coordinator._store.async_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_clears_snapshot(
        self, coordinator: HondaGeneratorCoordinator
    ) -> None:
        coordinator._stored_runtime_hours = 200
        coordinator._service_records = {}
        coordinator._service_due_dates = {"oil_change": "2026-01-01T00:00:00+00:00"}

        await coordinator.async_mark_service_complete(ServiceType.OIL_CHANGE)

        assert "oil_change" not in coordinator._service_due_dates
