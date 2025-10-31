from datetime import datetime
import pytz
from src.tools.tz_convertor import get_current_time, get_shifted_time, convert_time

def test_get_current_time():
    result = get_current_time("UTC")
    assert isinstance(result, dict)
    assert "current_time" in result
    assert "shifted_time" in result
    assert "timezone" in result
    assert "current_datetime" in result
    assert "shifted_datetime" in result
    assert result["timezone"] == "UTC"
    assert len(result["current_time"].split(":")) == 2
    assert result["current_time"] == result["shifted_time"]

def test_get_shifted_time():
    result = get_shifted_time("UTC", 2)
    assert isinstance(result, dict)
    assert "current_time" in result
    assert "shifted_time" in result
    assert "timezone" in result
    assert "current_datetime" in result
    assert "shifted_datetime" in result
    assert result["timezone"] == "UTC"

    current_hour = int(result["current_time"].split(":")[0])
    shifted_hour = int(result["shifted_time"].split(":")[0])

    assert (shifted_hour - current_hour) % 24 == 2

def test_get_shifted_time_negative():
    result = get_shifted_time("UTC", -2)
    assert isinstance(result, dict)
    assert "current_time" in result
    assert "shifted_time" in result
    assert "timezone" in result
    assert "current_datetime" in result
    assert "shifted_datetime" in result
    assert result["timezone"] == "UTC"

    current_hour = int(result["current_time"].split(":")[0])
    shifted_hour = int(result["shifted_time"].split(":")[0])
    
    assert (current_hour - shifted_hour) % 24 == 2

def test_convert_time():
    result = convert_time("14:30", "Europe/Berlin", "Asia/Tokyo")
    assert isinstance(result, dict)
    assert "time" in result
    assert "timezone" in result
    assert "datetime" in result
    assert result["timezone"] == "Asia/Tokyo"

def test_convert_time_same_timezone():
    time = "14:30"
    timezone = "Europe/Berlin"
    result = convert_time(time, timezone, timezone)
    assert result["time"] == time
    assert result["timezone"] == timezone

def test_invalid_timezone():
    import pytest
    with pytest.raises(pytz.exceptions.UnknownTimeZoneError):
        get_current_time("Invalid/Timezone")

def test_invalid_time_format():
    import pytest
    with pytest.raises(ValueError):
        convert_time("25:00", "Europe/Berlin", "UTC")

def test_timezone_conversion_accuracy():
    berlin_time = "14:30"
    result = convert_time(berlin_time, "Europe/Berlin", "UTC")
    
    berlin_tz = pytz.timezone("Europe/Berlin")
    utc_tz = pytz.timezone("UTC")
    
    current_date = datetime.now().date()
    berlin_dt = datetime.strptime(berlin_time, "%H:%M")
    berlin_dt = datetime.combine(current_date, berlin_dt.time())
    berlin_dt = berlin_tz.localize(berlin_dt)
    expected_utc = berlin_dt.astimezone(utc_tz)
    
    result_dt = datetime.fromisoformat(result["datetime"])
    assert abs((result_dt - expected_utc).total_seconds()) < 1 