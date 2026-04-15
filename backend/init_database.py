"""
Initialize the database - create all tables
Run this script once to set up the database
"""
from database import init_db, engine, Base
import models  # Import models to register them

if __name__ == "__main__":
    print("🗄️  Initializing IntelliMeet AI Database...")
    print("")
    
    # Create all tables
    init_db()
    
    print("")
    print("✅ Database setup complete!")
    print("📊 Tables created:")
    print("   - jobs")
    print("   - candidates")
    print("   - interviews")
    print("   - form_watchers")
    print("   - activity_logs")
    print("")
    print("You can now start the backend server!")
