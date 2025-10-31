from datetime import datetime, timedelta
import pytz

def get_current_time(time_zone: str) -> dict:
    """Gets the current time in the specified timezone.

    Args:
        time_zone (str): Target timezone (e.g. "Europe/Berlin", "America/New_York", "Asia/Tokyo")

    Returns:
        dict: Dictionary containing time information with keys:
            - time: str in format "HH:MM"
            - timezone: str name of the timezone
            - datetime: str ISO format datetime

    Example:
        get_current_time("Europe/Berlin") -> {
            "time": "14:30",
            "timezone": "Europe/Berlin",
            "datetime": "2024-03-20T14:30:00+01:00"
        }
    """
    return get_shifted_time(time_zone, 0)

def get_shifted_time(time_zone: str, shift_hours: int) -> dict:
    """Gets the current time and shifted time in the specified timezone.

    Args:
        time_zone (str): Target timezone (e.g. "Europe/Berlin", "America/New_York", "Asia/Tokyo")
        shift_hours (int): Number of hours to shift the time (positive for future, negative for past)

    Returns:
        dict: Dictionary containing time information with keys:
            - current_time: str in format "HH:MM"
            - shifted_time: str in format "HH:MM"
            - timezone: str name of the timezone
            - current_datetime: str ISO format datetime
            - shifted_datetime: str ISO format datetime

    Example:
        get_shifted_time("Europe/Berlin", 2) -> {
            "current_time": "14:30",
            "shifted_time": "16:30",
            "timezone": "Europe/Berlin",
            "current_datetime": "2024-03-20T14:30:00+01:00",
            "shifted_datetime": "2024-03-20T16:30:00+01:00"
        }
    """
    time_obj = datetime.now(pytz.UTC)
    tz_out_obj = pytz.timezone(time_zone)
    current_time = time_obj.astimezone(tz_out_obj)
    shifted_time = current_time + timedelta(hours=shift_hours)

    return {
        "current_time": current_time.strftime("%H:%M"),
        "shifted_time": shifted_time.strftime("%H:%M"),
        "timezone": time_zone,
        "current_datetime": current_time.isoformat(),
        "shifted_datetime": shifted_time.isoformat()
    }

def convert_time(
    time_in: str,
    tz_in: str,
    tz_out: str
) -> dict:
    """Converts time between different time zones.

    Args:
        time_in (str): Time to convert in format "HH:MM" (24-hour).
        tz_in (str): Source timezone (e.g. "Europe/Berlin", "America/New_York")
        tz_out (str): Target timezone (e.g. "Asia/Tokyo", "Europe/London")

    Returns:
        dict: Dictionary containing time information with keys:
            - time: str in format "HH:MM"
            - timezone: str name of the timezone
            - datetime: str ISO format datetime

    Example:
        convert_time("14:30", "Europe/Berlin", "Asia/Tokyo") -> {
            "time": "21:30",
            "timezone": "Asia/Tokyo",
            "datetime": "2024-03-20T21:30:00+09:00"
        }
    """
    tz_out_obj = pytz.timezone(tz_out)
    tz_in_obj = pytz.timezone(tz_in)
    current_date = datetime.now().date()
    time_obj = datetime.strptime(time_in, "%H:%M")
    time_obj = datetime.combine(current_date, time_obj.time())
    time_obj = tz_in_obj.localize(time_obj)
    time_out = time_obj.astimezone(tz_out_obj)

    return {
        "time": time_out.strftime("%H:%M"),
        "timezone": tz_out,
        "datetime": time_out.isoformat()
    }

if __name__ == "__main__":
    result = convert_time("14:11", "Europe/Berlin", "Asia/Nicosia")
    print(result)