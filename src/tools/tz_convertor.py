from datetime import datetime
import pytz

def convert_time(
    time_in: str,
    tz_in: str, 
    tz_out: str
) -> str:
    """Converts time between different time zones.
    
    Args:
        time_in (str): Time to convert in format "HH:MM" (24-hour)
        tz_in (str): Source timezone (e.g. "Europe/Berlin", "America/New_York")
        tz_out (str): Target timezone (e.g. "Asia/Tokyo", "Europe/London")

    Returns:
        str: converted time in format "HH:MM" (24-hour)

    Example:
        convert_time("14:30", "Europe/Berlin", "Asia/Tokyo") -> "21:30"
    """
    tz_in_obj = pytz.timezone(tz_in)
    tz_out_obj = pytz.timezone(tz_out)
    
    current_date = datetime.now().date()
    
    time_obj = datetime.strptime(time_in, "%H:%M") 
    time_obj = datetime.combine(current_date, time_obj.time())
    
    time_obj = tz_in_obj.localize(time_obj)
    
    time_out = time_obj.astimezone(tz_out_obj)
    
    return time_out.strftime("%H:%M")

if __name__ == "__main__":
    result = convert_time("14:11", "Europe/Berlin", "Asia/Nicosia")
    print(result)