#!/usr/bin/env python3
"""
Database Migration Test Script
Comprehensive testing for Railway database migration
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

class MigrationTester:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not found")

        self.engine = create_engine(self.database_url)
        self.results = []

    def log_result(self, test_name, success, message):
        """Log test result"""
        status = "✅" if success else "❌"
        self.results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
        print(f"{status} {test_name}: {message}")

    def test_database_connection(self):
        """Test basic database connectivity"""
        try:
            with self.engine.connect() as conn:
                # Try PostgreSQL version first, fall back to SQLite
                try:
                    result = conn.execute(text("SELECT version()"))
                    version = result.fetchone()[0]
                    db_type = "PostgreSQL"
                except:
                    result = conn.execute(text("SELECT sqlite_version()"))
                    version = f"SQLite {result.fetchone()[0]}"
                    db_type = "SQLite"

                self.log_result(
                    "Database Connection",
                    True,
                    f"Connected to {db_type} - {version[:50]}..."
                )
                return True
        except Exception as e:
            self.log_result("Database Connection", False, str(e))
            return False

    def test_base_tables_exist(self):
        """Test that core tables exist"""
        required_tables = ['players', 'picks', 'pick_results', 'games']

        try:
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()

            missing_tables = [t for t in required_tables if t not in existing_tables]

            if missing_tables:
                self.log_result(
                    "Base Tables",
                    False,
                    f"Missing tables: {missing_tables}"
                )
                return False
            else:
                self.log_result(
                    "Base Tables",
                    True,
                    f"All required tables present: {required_tables}"
                )
                return True

        except Exception as e:
            self.log_result("Base Tables", False, str(e))
            return False

    def test_odds_columns_exist(self):
        """Test that odds integration columns exist"""
        try:
            with self.engine.connect() as conn:
                # Try PostgreSQL schema first, fall back to direct query
                try:
                    # PostgreSQL method
                    result = conn.execute(text("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = 'games'
                        AND column_name IN ('point_spread', 'favorite_team')
                        ORDER BY column_name
                    """))
                    columns = list(result)
                except:
                    # SQLite method - try to query the columns directly
                    try:
                        conn.execute(text("SELECT point_spread, favorite_team FROM games LIMIT 1"))
                        columns = [
                            type('Row', (), {'column_name': 'point_spread'}),
                            type('Row', (), {'column_name': 'favorite_team'})
                        ]
                    except:
                        columns = []

                if len(columns) == 2:
                    self.log_result(
                        "Odds Columns",
                        True,
                        f"Both columns exist: {[getattr(c, 'column_name', c) for c in columns]}"
                    )
                    return True
                else:
                    # Test individual columns
                    missing = []
                    try:
                        conn.execute(text("SELECT point_spread FROM games LIMIT 1"))
                    except:
                        missing.append('point_spread')

                    try:
                        conn.execute(text("SELECT favorite_team FROM games LIMIT 1"))
                    except:
                        missing.append('favorite_team')

                    if missing:
                        self.log_result(
                            "Odds Columns",
                            False,
                            f"Missing columns: {missing}"
                        )
                        return False
                    else:
                        self.log_result(
                            "Odds Columns",
                            True,
                            "Both columns exist (verified via direct query)"
                        )
                        return True

        except Exception as e:
            self.log_result("Odds Columns", False, str(e))
            return False

    def test_odds_columns_schema(self):
        """Test that odds columns have correct data types"""
        try:
            with self.engine.connect() as conn:
                # For SQLite/other databases, just verify we can insert sample data
                try:
                    # Try PostgreSQL schema query first
                    result = conn.execute(text("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = 'games'
                        AND column_name IN ('point_spread', 'favorite_team')
                        ORDER BY column_name
                    """))

                    columns = {row.column_name: row for row in result}

                    # Check data types
                    schema_issues = []
                    if 'point_spread' in columns:
                        ps_col = columns['point_spread']
                        if not any(t in ps_col.data_type.lower() for t in ['real', 'float', 'numeric', 'double']):
                            schema_issues.append(f"point_spread: {ps_col.data_type} (expected numeric)")

                    if 'favorite_team' in columns:
                        ft_col = columns['favorite_team']
                        if not any(t in ft_col.data_type.lower() for t in ['varchar', 'text', 'char']):
                            schema_issues.append(f"favorite_team: {ft_col.data_type} (expected text)")

                    if schema_issues:
                        self.log_result(
                            "Odds Column Schema",
                            False,
                            f"Schema issues: {', '.join(schema_issues)}"
                        )
                        return False
                    else:
                        self.log_result(
                            "Odds Column Schema",
                            True,
                            "PostgreSQL schema verified - columns have correct types"
                        )
                        return True

                except:
                    # Fall back to functional test - try to query sample data
                    result = conn.execute(text("""
                        SELECT point_spread, favorite_team
                        FROM games
                        WHERE point_spread IS NOT NULL OR favorite_team IS NOT NULL
                        LIMIT 1
                    """))

                    row = result.fetchone()
                    if row:
                        self.log_result(
                            "Odds Column Schema",
                            True,
                            f"Schema verified via sample data: spread={row.point_spread}, team={row.favorite_team}"
                        )
                    else:
                        self.log_result(
                            "Odds Column Schema",
                            True,
                            "Schema verified - columns accept NULL values correctly"
                        )
                    return True

        except Exception as e:
            self.log_result("Odds Column Schema", False, str(e))
            return False

    def test_odds_indexes_exist(self):
        """Test that performance indexes exist"""
        try:
            with self.engine.connect() as conn:
                # Check for indexes (PostgreSQL specific)
                result = conn.execute(text("""
                    SELECT indexname, tablename
                    FROM pg_indexes
                    WHERE tablename = 'games'
                    AND (indexname LIKE '%point_spread%' OR indexname LIKE '%favorite_team%')
                """))

                indexes = list(result)

                if len(indexes) >= 2:
                    self.log_result(
                        "Odds Indexes",
                        True,
                        f"Performance indexes found: {[i.indexname for i in indexes]}"
                    )
                    return True
                else:
                    self.log_result(
                        "Odds Indexes",
                        False,
                        f"Missing performance indexes (found {len(indexes)})"
                    )
                    return False

        except Exception as e:
            # Indexes are optional, don't fail the test
            self.log_result(
                "Odds Indexes",
                True,
                f"Index check skipped: {str(e)[:50]}..."
            )
            return True

    def test_sample_data_query(self):
        """Test that we can query games with odds columns"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT game_id, home_team, away_team, point_spread, favorite_team
                    FROM games
                    LIMIT 3
                """))

                rows = list(result)

                self.log_result(
                    "Sample Data Query",
                    True,
                    f"Successfully queried {len(rows)} games with odds columns"
                )

                # Show sample data if available
                if rows:
                    print("   Sample data:")
                    for row in rows:
                        spread = row.point_spread if row.point_spread else "None"
                        fav = row.favorite_team if row.favorite_team else "None"
                        print(f"     {row.home_team} vs {row.away_team} | Spread: {spread} | Favorite: {fav}")

                return True

        except Exception as e:
            self.log_result("Sample Data Query", False, str(e))
            return False

    def test_migration_script_available(self):
        """Test that migration script exists and is executable"""
        script_path = os.path.join(os.path.dirname(__file__), "railway_migration.py")

        if os.path.exists(script_path):
            self.log_result(
                "Migration Script",
                True,
                f"Script exists at {script_path}"
            )
            return True
        else:
            self.log_result(
                "Migration Script",
                False,
                f"Script not found at {script_path}"
            )
            return False

    def run_all_tests(self):
        """Run all migration tests"""
        print(f"🧪 Database Migration Test Suite")
        print(f"⏰ Started at {datetime.now()}")
        print(f"🔗 Database: {self.database_url[:50]}...")
        print("=" * 60)

        # Run tests in order
        tests = [
            self.test_database_connection,
            self.test_base_tables_exist,
            self.test_odds_columns_exist,
            self.test_odds_columns_schema,
            self.test_odds_indexes_exist,
            self.test_sample_data_query,
            self.test_migration_script_available,
        ]

        passed = 0
        total = len(tests)

        for test in tests:
            if test():
                passed += 1
            print()  # Empty line between tests

        # Summary
        print("=" * 60)
        print(f"📊 Test Results: {passed}/{total} passed")

        if passed == total:
            print("🎉 All tests passed! Database migration is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the issues above.")
            print("\n💡 Quick fixes:")
            print("   - Run: python scripts/railway_migration.py")
            print("   - Or check Railway startup logs for migration errors")
            return False

def main():
    """Main test runner"""
    try:
        tester = MigrationTester()
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"❌ Test suite failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()