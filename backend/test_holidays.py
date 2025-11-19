"""Test script to verify holidays library is working."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import holidays
    print("[OK] Holidays library imported successfully")
    
    # Test US holidays
    us_holidays = holidays.UnitedStates(years=range(2024, 2026))
    print("[OK] US holidays initialized for 2024-2025")
    
    # Check for a known holiday
    from datetime import date
    thanksgiving_2024 = date(2024, 11, 28)
    if thanksgiving_2024 in us_holidays:
        print(f"[OK] Found Thanksgiving 2024: {us_holidays[thanksgiving_2024]}")
    
    christmas_2024 = date(2024, 12, 25)
    if christmas_2024 in us_holidays:
        print(f"[OK] Found Christmas 2024: {us_holidays[christmas_2024]}")
    
    # Get upcoming holidays
    today = date.today()
    upcoming = []
    for i in range(365):
        check_date = date.fromordinal(today.toordinal() + i)
        if check_date in us_holidays:
            upcoming.append((check_date, us_holidays[check_date]))
            if len(upcoming) >= 5:
                break
    
    print(f"[OK] Found {len(upcoming)} upcoming holidays:")
    for holiday_date, holiday_name in upcoming[:5]:
        print(f"   - {holiday_date}: {holiday_name}")
    
    print("\n[OK] All tests passed! Holidays library is working correctly.")
    
except ImportError as e:
    print(f"[ERROR] Holidays library not found: {e}")
    print("   Please install it with: pip install holidays==0.36")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

