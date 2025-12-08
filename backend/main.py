import os
import shutil
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import JWTError, jwt
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from ingest import ingest_file  # Expects ingest_file(path, owner)

load_dotenv()

app = FastAPI()

SECRET_KEY = "SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class DocumentSelection(BaseModel):
    filenames: List[str]

class UserCredentials(BaseModel):
    username: str
    password: str

class User(BaseModel):
    username: str

# --- HELPERS ---
def load_json_db(filename):
    if not os.path.exists(filename): return []
    try:
        with open(filename, "r") as f: return json.load(f)
    except: return []

def save_json_db(filename, data):
    with open(filename, "w") as f: json.dump(data, f, indent=4)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise credentials_exception
    except JWTError: raise credentials_exception
    
    users = load_json_db("users.json")
    user_data = next((u for u in users if u["username"] == username), None)
    if user_data is None: raise credentials_exception
    return User(username=user_data["username"])

# --- ROUTES ---

@app.post("/signup")
def signup(creds: UserCredentials):
    users = load_json_db("users.json")
    if any(u['username'] == creds.username for u in users):
        raise HTTPException(status_code=400, detail="Username already taken")
    users.append(creds.dict())
    save_json_db("users.json", users)
    return {"message": "Ranger registered successfully"}

@app.post("/login")
def login(creds: UserCredentials):
    users = load_json_db("users.json")
    user = next((u for u in users if u['username'] == creds.username and u['password'] == creds.password), None)
    if user:
        return {"token": create_access_token(data={"sub": user["username"]}), "username": user['username']}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

# --- SECURE DOCUMENT ENDPOINTS ---

@app.get("/documents")
def list_documents(current_user: User = Depends(get_current_user)):
    docs = load_json_db("doc_store.json")
    # FILTER: Only show docs owned by the logged-in user
    return [d for d in docs if d.get("owner") == current_user.username]

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...), 
    current_user: User = Depends(get_current_user) # Require Login
):
    temp_filename = f"temp_{file.filename}"
    with open(temp_filename, "wb") as buffer: 
        shutil.copyfileobj(file.file, buffer)
    
    # PASS USERNAME TO INGEST (Fixes public file issue)
    result = ingest_file(temp_filename, current_user.username)
    
    if os.path.exists(temp_filename): 
        os.remove(temp_filename)
    return result

@app.get("/search")
def search_documents(query: str):
    if not os.path.exists("faiss_index"): return {"answer": "System offline. Please upload a document first."}
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    
    # STRICTLY KEPT: gemini-flash-latest
    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
    qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=vector_store.as_retriever(), return_source_documents=True)
    response = qa_chain.invoke({"query": query})
    return {"answer": response['result'], "citation": f"Source: Page {response['source_documents'][0].metadata.get('page', 'Unknown')}"}

@app.post("/cross-summary")
def generate_cross_summary(selection: DocumentSelection):
    all_docs = load_json_db("doc_store.json")
    selected_docs = [d for d in all_docs if d['filename'] in selection.filenames]
    
    if not selected_docs: return {"cross_summary": "No matching documents found in selection."}

    combined_text = ""
    for d in selected_docs: combined_text += f"- File: {d['filename']} ({d['category']}): {d.get('summary', '')}\n"
    
    # STRICTLY KEPT: gemini-flash-latest
    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
    prompt = f"You are an Intelligence Analyst. Write a connection report based ONLY on these documents:\n{combined_text}\nIdentify relationships and combine information."
    
    response = llm.invoke(prompt)
    return {"cross_summary": response.content}


# import os
# import shutil
# import json
# from datetime import datetime, timedelta
# from typing import List, Optional

# # --- IMPORTS ---
# from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.security import OAuth2PasswordBearer
# from pydantic import BaseModel
# from jose import JWTError, jwt
# from dotenv import load_dotenv

# # --- AI IMPORTS ---
# from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# from langchain.chains import RetrievalQA
# from langchain_community.vectorstores import FAISS
# from ingest import ingest_file  # Expects ingest_file(path, owner)

# load_dotenv()

# app = FastAPI()

# # --- SECURITY CONFIG ---
# SECRET_KEY = "SECRET_KEY"  # In production, make this random
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 60
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# # Enable CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --- DATA MODELS ---
# class DocumentSelection(BaseModel):
#     filenames: List[str]

# class UserCredentials(BaseModel):
#     username: str
#     password: str

# class User(BaseModel):
#     username: str

# # --- DB HELPERS ---
# def load_json_db(filename):
#     if not os.path.exists(filename): return []
#     try:
#         with open(filename, "r") as f: return json.load(f)
#     except: return []

# def save_json_db(filename, data):
#     with open(filename, "w") as f: json.dump(data, f, indent=4)

# # --- SECURITY HELPERS ---
# def create_access_token(data: dict):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             raise credentials_exception
#     except JWTError:
#         raise credentials_exception
    
#     users = load_json_db("users.json")
#     user_data = next((u for u in users if u["username"] == username), None)
#     if user_data is None:
#         raise credentials_exception
#     return User(username=user_data["username"])

# # --- AUTH ENDPOINTS ---
# @app.post("/signup")
# def signup(creds: UserCredentials):
#     users = load_json_db("users.json")
#     if any(u['username'] == creds.username for u in users):
#         raise HTTPException(status_code=400, detail="Username already taken")
    
#     users.append(creds.dict())
#     save_json_db("users.json", users)
#     return {"message": "Ranger registered successfully"}

# @app.post("/login")
# def login(creds: UserCredentials):
#     users = load_json_db("users.json")
#     user = next((u for u in users if u['username'] == creds.username and u['password'] == creds.password), None)
    
#     if user:
#         # Generate REAL Token
#         access_token = create_access_token(data={"sub": user["username"]})
#         return {"token": access_token, "username": user['username']}
#     else:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

# # --- DOCUMENT ENDPOINTS ---

# @app.get("/documents")
# def list_documents(current_user: User = Depends(get_current_user)):
#     docs = load_json_db("doc_store.json")
    
#     # FILTER: Only show documents owned by this user
#     my_docs = [d for d in docs if d.get("owner") == current_user.username]
    
#     return [{"filename": d["filename"], "category": d["category"], "summary": d.get("summary", "No summary.")} for d in my_docs]

# @app.post("/upload")
# async def upload_document(
#     file: UploadFile = File(...), 
#     current_user: User = Depends(get_current_user) # Require Login
# ):
#     temp_filename = f"temp_{file.filename}"
#     with open(temp_filename, "wb") as buffer: 
#         shutil.copyfileobj(file.file, buffer)
    
#     # PASS USERNAME TO INGEST
#     result = ingest_file(temp_filename, current_user.username)
    
#     if os.path.exists(temp_filename): 
#         os.remove(temp_filename)
#     return result

# @app.get("/search")
# def search_documents(query: str):
#     if not os.path.exists("faiss_index"): return {"answer": "System offline. Please upload a document first."}
    
#     embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
#     vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    
#     llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
#     qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=vector_store.as_retriever(), return_source_documents=True)
#     response = qa_chain.invoke({"query": query})
#     return {"answer": response['result'], "citation": f"Source: Page {response['source_documents'][0].metadata.get('page', 'Unknown')}"}

# @app.post("/cross-summary")
# def generate_cross_summary(selection: DocumentSelection):
#     all_docs = load_json_db("doc_store.json")
#     selected_docs = [d for d in all_docs if d['filename'] in selection.filenames]
    
#     if not selected_docs: return {"cross_summary": "No matching documents found in selection."}

#     combined_text = ""
#     for d in selected_docs: combined_text += f"- File: {d['filename']} ({d['category']}): {d['summary']}\n"
    
#     llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
#     prompt = f"You are an Intelligence Analyst. Write a connection report based ONLY on these documents:\n{combined_text}\nIdentify relationships and combine information."
    
#     response = llm.invoke(prompt)
#     return {"cross_summary": response.content}

# import os
# import shutil
# import json
# from datetime import datetime, timedelta
# from typing import List, Optional

# # --- IMPORTS ---
# from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# from pydantic import BaseModel
# from jose import JWTError, jwt
# from dotenv import load_dotenv

# # --- IMPORT YOUR INGEST ENGINE ---
# from ingest import ingest_file  # Uses your strictly preserved ingest.py

# load_dotenv()

# app = FastAPI()

# # --- SECURITY CONFIG ---
# SECRET_KEY = "SECRET_KEY"
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 60
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# # Files
# USERS_FILE = "users.json"
# DB_FILE = "doc_store.json"

# # --- CORS ---
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --- MODELS ---
# class UserCredentials(BaseModel):
#     username: str
#     password: str
#     email: Optional[str] = None

# class User(BaseModel):
#     username: str
#     email: Optional[str] = None

# # --- HELPERS ---
# def create_access_token(data: dict):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# def load_json_db(filename):
#     if not os.path.exists(filename): return []
#     try:
#         with open(filename, "r") as f: return json.load(f)
#     except: return []

# def save_json_db(filename, data):
#     with open(filename, "w") as f: json.dump(data, f, indent=4)

# # --- AUTH ---
# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None: raise credentials_exception
#     except JWTError: raise credentials_exception
    
#     users = load_json_db(USERS_FILE)
#     user_data = next((u for u in users if u["username"] == username), None)
#     if user_data is None: raise credentials_exception
#     return User(**user_data)

# # --- ROUTES ---

# @app.post("/signup")
# def signup(creds: UserCredentials):
#     users = load_json_db(USERS_FILE)
#     if any(u['username'] == creds.username for u in users):
#         raise HTTPException(status_code=400, detail="Username taken")
#     users.append(creds.dict())
#     save_json_db(USERS_FILE, users)
#     return {"message": "Success"}

# @app.post("/login")
# def login(creds: UserCredentials):
#     users = load_json_db(USERS_FILE)
#     user = next((u for u in users if (u['username'] == creds.username or u.get('email') == creds.username) and u['password'] == creds.password), None)
#     if user:
#         return {"token": create_access_token(data={"sub": user["username"]}), "username": user['username']}
#     raise HTTPException(status_code=401, detail="Invalid credentials")

# @app.get("/documents")
# async def get_documents(current_user: User = Depends(get_current_user)):
#     docs = load_json_db(DB_FILE)
#     # FILTER: Only show docs owned by this user
#     return [d for d in docs if d.get("owner") == current_user.username]

# @app.post("/upload")
# async def upload_file(
#     file: UploadFile = File(...), 
#     current_user: User = Depends(get_current_user)
# ):
#     # 1. Save locally
#     os.makedirs("uploaded_files", exist_ok=True)
#     file_location = f"uploaded_files/{file.filename}"
#     with open(file_location, "wb+") as f: shutil.copyfileobj(file.file, f)

#     category = "General"
#     summary = "AI processing skipped (Quota or Error)."

#     # 2. RUN INGESTION (Your ingest.py)
#     try:
#         # Call your unchanged ingest function
#         result = ingest_file(file_location)
        
#         if "error" in result:
#             print(f"Ingest Warning: {result['error']}")
#             # Fallback values if API failed
#             category = "General"
#             summary = f"Uploaded by {current_user.username} (AI Offline)"
#             # We must manually save to DB since ingest.py skips save on error
#             save_manual_record = True
#         else:
#             # Success! ingest.py already saved the record, BUT it missed the 'owner' field.
#             category = result.get("category", "General")
#             summary = result.get("summary", "No summary.")
#             save_manual_record = False 
            
#             # 3. POST-PROCESS: Add Owner to the record created by ingest.py
#             docs = load_json_db(DB_FILE)
#             for d in docs:
#                 if d["filename"] == file.filename:
#                     d["owner"] = current_user.username  # <--- ATTACH OWNER TAG
#                     d["upload_date"] = str(datetime.now())
#             save_json_db(DB_FILE, docs)

#     except Exception as e:
#         print(f"Critical Ingest Error: {e}")
#         save_manual_record = True

#     # 4. MANUAL SAVE (If AI failed completely)
#     if save_manual_record:
#         new_doc = {
#             "filename": file.filename,
#             "category": category,
#             "summary": summary,
#             "owner": current_user.username,
#             "upload_date": str(datetime.now())
#         }
#         docs = load_json_db(DB_FILE)
#         # Remove old duplicate if exists
#         docs = [d for d in docs if d['filename'] != file.filename]
#         docs.append(new_doc)
#         save_json_db(DB_FILE, docs)

#     return {"filename": file.filename, "category": category}

# # --- AI SEARCH ROUTES ---
# # These mock endpoints keep the frontend running even if AI is unstable
# @app.get("/search")
# def search_documents(query: str):
#     # You can connect your real FAISS search here later if desired
#     return {"answer": f"Simulated result for: {query}", "citation": "Database"}

# class DocumentSelection(BaseModel):
#     filenames: List[str]

# @app.post("/cross-summary")
# def generate_cross_summary(selection: DocumentSelection):
#     return {"cross_summary": "Simulated connection report."}

# import os
# import shutil
# import json
# from datetime import datetime, timedelta
# from typing import List, Optional
# from ingest import ingest_file

# # --- FIXED IMPORTS ---
# from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.security import OAuth2PasswordBearer
# from pydantic import BaseModel
# from jose import JWTError, jwt
# from dotenv import load_dotenv

# # --- AI IMPORTS (Kept from your code) ---
# # Note: These will only work if you have the API keys set in .env
# from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# from langchain.chains import RetrievalQA
# from langchain_community.vectorstores import FAISS
# # from ingest import ingest_file  <-- Kept commented as requested (or uncomment if you have the file)

# load_dotenv()

# app = FastAPI()

# # --- SECURITY CONFIGURATION (REQUIRED FOR LOGIN) ---
# SECRET_KEY = "SECRET_KEY"  # Change this in production
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 60

# # This tells FastAPI where to look for the token
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# # Database Files
# USERS_FILE = "users.json"
# DB_FILE = "doc_store.json"

# # --- CORS SETUP ---
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --- MODELS ---
# class UserCredentials(BaseModel):
#     username: str
#     password: str
#     email: Optional[str] = None

# class User(BaseModel):
#     username: str
#     email: Optional[str] = None

# # --- HELPER FUNCTIONS ---
# def create_access_token(data: dict):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt

# def load_json_db(filename):
#     if not os.path.exists(filename): return []
#     try:
#         with open(filename, "r") as f: return json.load(f)
#     except: return []

# def save_json_db(filename, data):
#     with open(filename, "w") as f: json.dump(data, f, indent=4)

# # --- AUTH DEPENDENCY (FIXED) ---
# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             raise credentials_exception
#     except JWTError:
#         raise credentials_exception
    
#     # Check if user exists
#     if os.path.exists(USERS_FILE):
#         with open(USERS_FILE, "r") as f:
#             users_db = json.load(f)
#             # Find user
#             user_data = next((u for u in users_db if u["username"] == username), None)
#             if user_data is None:
#                 raise credentials_exception
#             return User(**user_data)
    
#     raise credentials_exception

# # --- ROUTES ---

# @app.post("/signup")
# def signup(creds: UserCredentials):
#     users = load_json_db(USERS_FILE)
#     # Check if username exists
#     if any(u['username'] == creds.username for u in users):
#         raise HTTPException(status_code=400, detail="Username already taken")
    
#     users.append(creds.dict())
#     save_json_db(USERS_FILE, users)
#     return {"message": "Ranger registered successfully"}

# @app.post("/login")
# def login(creds: UserCredentials):
#     users = load_json_db(USERS_FILE)
#     # Check Username OR Email
#     user = next((u for u in users if (u['username'] == creds.username or u.get('email') == creds.username) and u['password'] == creds.password), None)
    
#     if user:
#         # Generate Real JWT Token
#         access_token = create_access_token(data={"sub": user["username"]})
#         return {"token": access_token, "username": user['username']}
#     else:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

# # --- DOCUMENT ENDPOINTS ---

# @app.get("/documents")
# async def get_documents(current_user: User = Depends(get_current_user)):
#     if not os.path.exists(DB_FILE):
#         return []
    
#     with open(DB_FILE, "r") as f:
#         try: docs = json.load(f)
#         except: return []
    
#     # FILTER: Only return docs owned by the logged-in user
#     my_docs = [d for d in docs if d.get("owner") == current_user.username]
    
#     return my_docs

# # --- YOUR ORIGINAL COMMENTED CODE (PRESERVED) ---
# # @app.get("/documents")
# # def list_documents():
# #     # This reads the doc_store.json to fill your sidebar
# #     docs = load_json_db("doc_store.json")
# #     return [{"filename": d["filename"], "category": d["category"], "summary": d.get("summary", "No summary.")} for d in docs]

# @app.post("/upload")
# async def upload_file(
#     file: UploadFile = File(...), 
#     current_user: User = Depends(get_current_user)
# ):
#     # 1. Save file locally
#     os.makedirs("uploaded_files", exist_ok=True)
#     file_location = f"uploaded_files/{file.filename}"
    
#     with open(file_location, "wb+") as file_object:
#         shutil.copyfileobj(file.file, file_object)

#     # 2. AI Processing (WITH SAFETY SHIELD)
#     print(f"Processing {file.filename}...")
#     try:
#         # Try to generate real summary & category
#         ingest_result = ingest_file(file_location)
#         category = ingest_result.get("category", "General")
#         summary = ingest_result.get("summary", "Summary generation failed (API Limit).")
#     except Exception as e:
#         print(f"AI Ingest Failed: {e}")
#         # Fallback if AI is broken/limit reached
#         category = "General"
#         summary = f"Uploaded by {current_user.username} (AI Processing Skipped)"

#     # 3. Create Record
#     new_doc = {
#         "filename": file.filename,
#         "category": category,
#         "summary": summary,
#         "owner": current_user.username,
#         "upload_date": str(datetime.now())
#     }

#     # 4. Save to DB
#     if os.path.exists(DB_FILE):
#         with open(DB_FILE, "r") as f:
#             try: docs = json.load(f)
#             except: docs = []
#     else:
#         docs = []

#     docs.append(new_doc)
    
#     with open(DB_FILE, "w") as f:
#         json.dump(docs, f, indent=4)

#     return {"filename": file.filename, "category": category}

# @app.post("/upload")
# async def upload_file(
#     file: UploadFile = File(...), 
#     current_user: User = Depends(get_current_user)
# ):
#     # 1. Save file locally
#     os.makedirs("uploaded_files", exist_ok=True)
#     file_location = f"uploaded_files/{file.filename}"
    
#     with open(file_location, "wb+") as file_object:
#         shutil.copyfileobj(file.file, file_object)

#     # 2. Tag with Owner
#     new_doc = {
#         "filename": file.filename,
#         "category": "General",
#         "summary": f"Uploaded by {current_user.username}",
#         "owner": current_user.username,
#         "upload_date": str(datetime.now())
#     }

#     # 3. Save to DB
#     if os.path.exists(DB_FILE):
#         with open(DB_FILE, "r") as f:
#             try: docs = json.load(f)
#             except: docs = []
#     else:
#         docs = []

#     docs.append(new_doc)
    
#     with open(DB_FILE, "w") as f:
#         json.dump(docs, f, indent=4)

#     return {"filename": file.filename, "category": "General"}

# --- YOUR ORIGINAL COMMENTED CODE (PRESERVED) ---
# @app.post("/upload")
# async def upload_document(file: UploadFile = File(...)):
#     temp_filename = f"temp_{file.filename}"
#     with open(temp_filename, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
#     result = ingest_file(temp_filename)
#     if os.path.exists(temp_filename): os.remove(temp_filename)
#     return result

# --- AI ROUTES (Kept Active but guarded against Import Errors) ---

# @app.get("/search")
# def search_documents(query: str):
#     if not os.path.exists("faiss_index"): return {"answer": "System offline. Please upload a document first."}
    
#     try:
#         embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
#         vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
#         llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
#         qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=vector_store.as_retriever(), return_source_documents=True)
#         response = qa_chain.invoke({"query": query})
#         return {"answer": response['result'], "citation": f"Source: Page {response['source_documents'][0].metadata.get('page', 'Unknown')}"}
#     except Exception as e:
#         print(f"AI Error: {e}")
#         return {"answer": "AI Service Unavailable (Quota or API Error)", "citation": "System"}

# class DocumentSelection(BaseModel):
#     filenames: List[str]

# @app.post("/cross-summary")
# def generate_cross_summary(selection: DocumentSelection):
#     all_docs = load_json_db(DB_FILE)
#     selected_docs = [d for d in all_docs if d['filename'] in selection.filenames]
    
#     if not selected_docs: return {"cross_summary": "No matching documents found in selection."}

#     combined_text = ""
#     for d in selected_docs: combined_text += f"- File: {d['filename']} ({d['category']}): {d.get('summary', '')}\n"
    
#     try:
#         llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
#         prompt = f"You are an Intelligence Analyst. Write a connection report based ONLY on these documents:\n{combined_text}\nIdentify relationships and combine information."
#         response = llm.invoke(prompt)
#         return {"cross_summary": response.content}
#     except Exception as e:
#         return {"cross_summary": "AI Service Unavailable (Quota or API Error)"}


# import os
# import shutil
# from typing import List
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from dotenv import load_dotenv
# from pymongo import MongoClient  # <--- DATABASE DRIVER
# from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# from langchain.chains import RetrievalQA
# from langchain_community.vectorstores import FAISS
# from ingest import ingest_file

# load_dotenv()

# app = FastAPI()

# # --- MONGODB CONNECTION ---
# # This reads the string you just pasted in .env
# MONGO_URI = os.getenv("MONGO_URI")
# client = MongoClient(MONGO_URI)
# db = client["ranger_intel_db"]  # Your Database Name
# users_col = db["users"]         # Collection for Login
# docs_col = db["documents"]      # Collection for Files

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# class DocumentSelection(BaseModel):
#     filenames: List[str]

# class UserCredentials(BaseModel):
#     username: str
#     password: str

# # --- AUTH (USING MONGODB) ---
# @app.post("/signup")
# def signup(creds: UserCredentials):
#     # Check Mongo for existing user
#     if users_col.find_one({"username": creds.username}):
#         raise HTTPException(status_code=400, detail="Username taken")
    
#     # Insert new user into Cloud
#     users_col.insert_one(creds.dict())
#     return {"message": "Ranger registered successfully"}

# @app.post("/login")
# def login(creds: UserCredentials):
#     # Find user in Cloud
#     user = users_col.find_one({"username": creds.username, "password": creds.password})
#     if user:
#         return {"token": "valid_ranger_token", "username": user['username']}
#     else:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

# # --- DOCUMENT MANAGEMENT (USING MONGODB) ---
# @app.get("/documents")
# def list_documents():
#     # Fetch all docs from Cloud, hide the Mongo ID
#     docs = list(docs_col.find({}, {"_id": 0}))
#     return docs

# @app.post("/upload")
# async def upload_document(file: UploadFile = File(...)):
#     temp_filename = f"temp_{file.filename}"
#     with open(temp_filename, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    
#     # Run AI Processing
#     result = ingest_file(temp_filename)
    
#     if os.path.exists(temp_filename): os.remove(temp_filename)
    
#     if "error" in result:
#         return result

#     # SAVE TO MONGODB
#     doc_data = {
#         "filename": result["filename"],
#         "category": result["category"],
#         "summary": result["summary"]
#     }
    
#     # Update if exists, otherwise Insert
#     docs_col.update_one(
#         {"filename": result["filename"]}, 
#         {"$set": doc_data}, 
#         upsert=True
#     )
    
#     return result

# # --- SEARCH & SUMMARY ---
# @app.get("/search")
# def search_documents(query: str):
#     if not os.path.exists("faiss_index"): return {"answer": "System offline."}
    
#     embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
#     vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
#     llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
#     qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=vector_store.as_retriever(), return_source_documents=True)
#     response = qa_chain.invoke({"query": query})
#     return {"answer": response['result'], "citation": f"Source: Page {response['source_documents'][0].metadata.get('page', 'Unknown')}"}

# @app.post("/cross-summary")
# def generate_cross_summary(selection: DocumentSelection):
#     # Fetch specific docs from Cloud
#     selected_docs = list(docs_col.find({"filename": {"$in": selection.filenames}}))
    
#     if not selected_docs: return {"cross_summary": "No documents found."}

#     combined_text = ""
#     for d in selected_docs: combined_text += f"- File: {d['filename']} ({d['category']}): {d['summary']}\n"
    
#     llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
#     prompt = f"Write a connection report:\n{combined_text}"
#     response = llm.invoke(prompt)
#     return {"cross_summary": response.content}






# import os
# import shutil
# import json
# from typing import List
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from dotenv import load_dotenv
# from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# from langchain.chains import RetrievalQA
# from langchain_community.vectorstores import FAISS
# from ingest import ingest_file

# load_dotenv()

# app = FastAPI()

# # Enable CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --- DATA MODELS ---
# class DocumentSelection(BaseModel):
#     filenames: List[str]

# class UserCredentials(BaseModel):
#     username: str
#     password: str

# # --- DB HELPERS ---
# def load_json_db(filename):
#     if not os.path.exists(filename): return []
#     try:
#         with open(filename, "r") as f: return json.load(f)
#     except: return []

# def save_json_db(filename, data):
#     with open(filename, "w") as f: json.dump(data, f, indent=4)

# # --- AUTH ENDPOINTS ---
# @app.post("/signup")
# def signup(creds: UserCredentials):
#     users = load_json_db("users.json")
#     # Check if username exists
#     if any(u['username'] == creds.username for u in users):
#         raise HTTPException(status_code=400, detail="Username already taken")
    
#     users.append(creds.dict())
#     save_json_db("users.json", users)
#     return {"message": "Ranger registered successfully"}

# @app.post("/login")
# def login(creds: UserCredentials):
#     users = load_json_db("users.json")
#     user = next((u for u in users if u['username'] == creds.username and u['password'] == creds.password), None)
    
#     if user:
#         # Return a simple token (in production, use JWT)
#         return {"token": "valid_ranger_token", "username": user['username']}
#     else:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

# # --- CORE ENDPOINTS ---
# @app.get("/documents")
# def list_documents():
#     docs = load_json_db("doc_store.json")
#     return [{"filename": d["filename"], "category": d["category"], "summary": d.get("summary", "No summary.")} for d in docs]

# @app.post("/upload")
# async def upload_document(file: UploadFile = File(...)):
#     temp_filename = f"temp_{file.filename}"
#     with open(temp_filename, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
#     result = ingest_file(temp_filename)
#     if os.path.exists(temp_filename): os.remove(temp_filename)
#     return result

# @app.get("/search")
# def search_documents(query: str):
#     if not os.path.exists("faiss_index"): return {"answer": "System offline. Please upload a document first."}
    
#     embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
#     vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    
#     llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
#     qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=vector_store.as_retriever(), return_source_documents=True)
#     response = qa_chain.invoke({"query": query})
    
#     return {"answer": response['result'], "citation": f"Source: Page {response['source_documents'][0].metadata.get('page', 'Unknown')}"}

# @app.post("/cross-summary")
# def generate_cross_summary(selection: DocumentSelection):
#     all_docs = load_json_db("doc_store.json")
#     selected_docs = [d for d in all_docs if d['filename'] in selection.filenames]
    
#     if not selected_docs: return {"cross_summary": "No matching documents found in selection."}

#     combined_text = ""
#     for d in selected_docs: combined_text += f"- File: {d['filename']} ({d['category']}): {d['summary']}\n"
    
#     llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
#     prompt = f"You are an Intelligence Analyst. Write a connection report based ONLY on these documents:\n{combined_text}\nIdentify relationships and combine information."
    
#     response = llm.invoke(prompt)
#     return {"cross_summary": response.content}




