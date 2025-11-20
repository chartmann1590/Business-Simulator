"""
PostgreSQL setup script for the Office Simulation application.

This script:
1. Checks if PostgreSQL is installed
2. Creates the database if it doesn't exist
3. Creates a user if needed (optional)
4. Tests the connection

Usage:
    python setup_postgresql.py

Environment variables:
    DATABASE_URL: PostgreSQL connection string (required, or use individual POSTGRES_* variables)
    POSTGRES_USER: PostgreSQL superuser (default: postgres)
    POSTGRES_PASSWORD: PostgreSQL password (required if DATABASE_URL not set)
    POSTGRES_HOST: PostgreSQL host (default: localhost)
    POSTGRES_PORT: PostgreSQL port (default: 5432)
    DB_NAME: Database name (default: office_db)
"""
import asyncio
import asyncpg
import os
import sys
import subprocess

# Configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "office_db")

# DATABASE_URL takes precedence, otherwise construct from individual components
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if not POSTGRES_PASSWORD:
        raise ValueError(
            "Either DATABASE_URL or POSTGRES_PASSWORD must be set in environment variables. "
            "Please set them in your .env file."
        )
    DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{DB_NAME}"

async def check_postgresql_installed() -> bool:
    """Check if PostgreSQL is installed and accessible."""
    try:
        # Try to run psql command
        result = subprocess.run(
            ["psql", "--version"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print(f"[OK] PostgreSQL found: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    except Exception as e:
        pass
    
    # Try to connect to PostgreSQL server
    try:
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database="postgres"  # Connect to default database
        )
        await conn.close()
        print("[OK] PostgreSQL server is running")
        return True
    except Exception as e:
        print(f"[ERROR] Cannot connect to PostgreSQL server: {e}")
        return False

async def create_database():
    """Create the database if it doesn't exist."""
    try:
        # Connect to PostgreSQL server (not the specific database)
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database="postgres"  # Connect to default database
        )
        
        # Check if database exists
        db_exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            DB_NAME
        )
        
        if db_exists:
            print(f"[OK] Database '{DB_NAME}' already exists")
        else:
            # Create database
            await conn.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"[OK] Created database '{DB_NAME}'")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Error creating database: {e}")
        print("\nYou may need to:")
        print(f"  1. Create the database manually: createdb -U {POSTGRES_USER} {DB_NAME}")
        print(f"  2. Or run as PostgreSQL superuser")
        return False

async def test_connection():
    """Test connection to the database."""
    try:
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=DB_NAME
        )
        
        # Test query
        version = await conn.fetchval("SELECT version()")
        print(f"[OK] Successfully connected to database '{DB_NAME}'")
        print(f"  PostgreSQL version: {version.split(',')[0]}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Error connecting to database: {e}")
        return False

async def setup_extensions():
    """Setup PostgreSQL extensions if needed."""
    try:
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=DB_NAME
        )
        
        # Enable uuid extension if needed (for future use)
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
            print("[OK] PostgreSQL extensions configured")
        except Exception:
            pass  # Extension might not be needed or already exists
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"[WARNING] Could not setup extensions: {e}")
        return False

async def main():
    """Main setup function."""
    print("=" * 60)
    print("PostgreSQL Setup for Office Simulation")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Host: {POSTGRES_HOST}")
    print(f"  Port: {POSTGRES_PORT}")
    print(f"  User: {POSTGRES_USER}")
    print(f"  Database: {DB_NAME}")
    print(f"  Connection URL: {DATABASE_URL.replace(POSTGRES_PASSWORD, '***')}")
    
    # Check if PostgreSQL is installed
    print("\n1. Checking PostgreSQL installation...")
    if not await check_postgresql_installed():
        print("\n[ERROR] PostgreSQL is not installed or not accessible.")
        print("\nPlease install PostgreSQL:")
        print("  Windows: Download from https://www.postgresql.org/download/windows/")
        print("  macOS:   brew install postgresql")
        print("  Linux:   sudo apt-get install postgresql (Ubuntu/Debian)")
        print("           sudo yum install postgresql (CentOS/RHEL)")
        print("\nAfter installation, make sure PostgreSQL service is running:")
        print("  Windows: Check Services panel")
        print("  macOS:   brew services start postgresql")
        print("  Linux:   sudo systemctl start postgresql")
        return False
    
    # Create database
    print("\n2. Creating database...")
    if not await create_database():
        return False
    
    # Setup extensions
    print("\n3. Setting up extensions...")
    await setup_extensions()
    
    # Test connection
    print("\n4. Testing connection...")
    if not await test_connection():
        return False
    
    print("\n" + "=" * 60)
    print("[OK] PostgreSQL setup completed successfully!")
    print("=" * 60)
    print(f"\nYou can now run the application with:")
    print(f"  DATABASE_URL={DATABASE_URL} python backend/main.py")
    print("\nOr set the DATABASE_URL environment variable.")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

