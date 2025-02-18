from scrapper import get_attendance_report
import logging

def test_attendance():
    username = "24L35A0524"
    password = "Vijay@4355"
    
    try:
        print("🔄 Fetching attendance report...")
        report = get_attendance_report(username, password)
        print("\n" + "="*50 + "\n")
        print(report)
        print("\n" + "="*50)
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_attendance()