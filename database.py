import psycopg2
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL


class Database:

    @staticmethod
    def get_connection():
        return psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor
        )

    @staticmethod
    def execute_fetchall(query, params=None):
        conn = Database.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)
            return cursor.fetchall()

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def execute_fetchone(query, params=None):
        conn = Database.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)
            return cursor.fetchone()

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def execute_commit(query, params=None):
        conn = Database.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)
            conn.commit()
            return True

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def test_connection():
        conn = Database.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT NOW();")
        print(cursor.fetchone())

        cursor.close()
        conn.close()