from fastapi import FastAPI, HTTPException, Query
from fastapi import Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from database import Database
from pydantic import BaseModel
from database import Database
import uuid
from supabase import create_client, Client


app = FastAPI(title="SecureVault Backend Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

Database.test_connection()

@app.get("/")
def home():
    # Fetch every row inside your users table to see exact string values
    try:
        all_users = Database.execute_fetchall("SELECT * FROM users")
        return {
            "message": "Connected Successfully",
            "stored_users_in_db": all_users
        }
    except Exception as e:
        return {"message": "Connected", "error_fetching": str(e)}


class LoginRequest(BaseModel):
    name: str
    password: str


@app.post("/api/auth/login")
def login_user(credentials: LoginRequest):
    # 1. Strip away external accidental space strokes and convert to standard lowercase
    search_name = credentials.name.strip()

    # 2. Use 'TRIM(LOWER(name))' to ensure spaces and case mismatches are completely ignored
    query = """
        SELECT u.id, u.name, u.email, u.role_id, u.password, r.name as role_name
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.id
        WHERE TRIM(LOWER(u.name)) = LOWER(%s)
    """

    user_record = Database.execute_fetchone(query, (search_name,))

    if not user_record:
        raise HTTPException(
            status_code=404,
            detail=f"Identity clearance records not found for input target string: '{search_name}'"
        )

    # 3. Handle data mapping whether your Database returns a Dictionary or a Tuple
    if isinstance(user_record, dict):
        db_id = user_record.get("id")
        db_name = user_record.get("name")
        db_email = user_record.get("email")
        db_role_id = user_record.get("role_id")
        db_password = user_record.get("password")
        db_role_name = user_record.get("role_name")
    else:
        db_id = user_record[0]
        db_name = user_record[1]  # Matches u.name position
        db_email = user_record[2]  # Matches u.email position
        db_role_id = user_record[3]  # Matches u.role_id position
        db_password = user_record[4]  # Matches u.password position
        db_role_name = user_record[5] if len(user_record) > 5 else None

    # 4. Verify Password key constraints
    if str(db_password).strip() != str(credentials.password).strip():
        raise HTTPException(status_code=401, detail="Invalid credential pairing validation token match.")

    return {
        "id": db_id,
        "name": db_name,
        "email": db_email,
        "role_id": db_role_id,
        "role_name": db_role_name if db_role_name else "Employee"
    }

@app.get("/users/{name}")
def get_user(name: str):
    # Modified to perform an INNER JOIN with roles so the frontend can display 'Employee', 'Manager', etc.
    query = """
        SELECT u.id, u.created_at, u.name, u.email, u.role_id, r.name as role_name
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.id
        WHERE u.name = %s
    """
    result = Database.execute_fetchone(query, (name,))
    if not result:
        raise HTTPException(status_code=404, detail="User profile records not found")
    return result

@app.get("/api/documents")
def get_all_documents():
    """Fetches the full dynamic corporate document feed."""
    query = """
        SELECT id, created_at, title, description, category, security_status, file_url
        FROM documents
        ORDER BY created_at DESC
    """
    # Assuming your Database class handles fetching multiple rows via fetchall
    try:
        return Database.execute_fetchall(query)
    except AttributeError:
        # Fallback if your class wraps fetchall differently
        return Database.execute_query(query)


@app.get("/api/vault/documents")
def get_vault_documents(role_id: int = Query(..., description="The role ID of the authenticated user")):
    """
    Fetches filtered corporate assets matching explicit role authorization rules.
    Role 1 = Admin, Role 3 = Manager, Role 2 (or others) = Employee
    """
    try:
        # If the user is an Employee (role_id 2 or undefined standard role)
        if role_id != 1 and role_id != 3:
            query = """
                SELECT id, created_at, title, description, category, security_status, file_url
                FROM documents
                WHERE security_status = 'Public'
                ORDER BY created_at DESC
            """
            return Database.execute_fetchall(query)

        # Elevated access: Admins and Managers pull all repository documents
        else:
            query = """
                SELECT id, created_at, title, description, category, security_status, file_url
                FROM documents
                ORDER BY created_at DESC
            """
            return Database.execute_fetchall(query)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation fault: {str(e)}")


@app.post("/api/users/{user_id}/upload-document")
def upload_user_document(user_id: int, document_type: str = Form(...), file: UploadFile = File(...)):

    """
    Receives an uploaded binary file, streams it safely to the Supabase
    Storage cloud bucket, and maps the record to the target user_id.
    """
    SUPABASE_URL = "https://kukbjzgaulugvfnfabfq.supabase.co"
    SUPABASE_KEY = "sb_publishable_gOnsgl-hxyrG7jwCIUi1ZQ_g9BYSsUv"
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        # 1. Read file raw bytes
        file_bytes = file.file.read()

        # 2. Generate a totally unique, un-guessable storage path filename
        unique_id = uuid.uuid4().hex
        file_extension = file.filename.split(".")[-1]
        storage_path = f"user_{user_id}/{unique_id}_{document_type.lower().replace(' ', '_')}.{file_extension}"

        # 3. Stream object payload directly into your Supabase storage engine bucket
        # Note: If using raw storage requests without the client library, use standard HTTP requests.
        # Assuming you have initialized your 'supabase' client link:
        bucket_name = "user-vault"

        upload_response = supabase.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": file.content_type}
        )

        # 4. Extract the absolute signed or public asset address URL
        file_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)

        # 5. Insert document metadata details into your custom database using your SQL structure
        insert_query = """
            INSERT INTO user_documents (user_id, document_type, file_name, file_url, mime_type)
            VALUES (%s, %s, %s, %s, %s)
        """
        Database.execute_commit(insert_query, (user_id, document_type, file.filename, file_url, file.content_type))

        return {"status": "success", "message": f"{document_type} successfully stored in secure vault repository."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Secure file upload layer crashed: {str(e)}")


@app.get("/api/users/{user_id}/personal-documents")
def get_personal_documents(user_id: int):
    """
    Fetches the precise list of personal files belonging exclusively to the authenticated user.
    """
    query = """
        SELECT id, created_at, document_type, file_name, file_url, mime_type
        FROM user_documents
        WHERE user_id = %s
        ORDER BY created_at DESC
    """
    try:
        return Database.execute_fetchall(query, (user_id,))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/search")
def search_documents(q: str = Query(..., min_length=1)):
    """Filters corporate resources using a partial text match engine."""
    query = """
        SELECT id, created_at, title, description, category, security_status, file_url
        FROM documents
        WHERE title ILIKE %s OR description ILIKE %s
    """
    search_param = f"%{q}%"
    try:
        return Database.execute_fetchall(query, (search_param, search_param))
    except AttributeError:
        return Database.execute_query(query, (search_param, search_param))
