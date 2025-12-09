import os
import shutil
import json
import pdfplumber  # --- NEW: Required for page-wise summary
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

# --- CONFIG ---
SECRET_KEY = "SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
UPLOAD_DIR = "uploaded_files"  # --- NEW: Where we save files permanently
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

# --- AUTH ROUTES ---

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

# --- DOCUMENT ROUTES ---

@app.get("/documents")
def list_documents(current_user: User = Depends(get_current_user)):
    docs = load_json_db("doc_store.json")
    # FILTER: Only show docs owned by the logged-in user
    return [d for d in docs if d.get("owner") == current_user.username]

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...), 
    current_user: User = Depends(get_current_user)
):
    # --- CHANGED: Save to permanent folder instead of temp ---
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    with open(file_path, "wb") as buffer: 
        shutil.copyfileobj(file.file, buffer)
    
    # Pass the PERMANENT path to ingest
    result = ingest_file(file_path, current_user.username)
    
    # We DO NOT delete the file anymore, so we can read it later for page-summary
    return result

# --- NEW ENDPOINT: PAGE-WISE SUMMARY ---
@app.post("/page-summary")
def generate_page_summary(selection: DocumentSelection):
    # We expect just ONE filename in the list for now
    if not selection.filenames:
        raise HTTPException(status_code=400, detail="No filename provided.")
        
    filename = selection.filenames[0]
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_path):
        # Fallback check for temp files if using old uploaded data
        if os.path.exists(f"temp_{filename}"):
            file_path = f"temp_{filename}"
        else:
            raise HTTPException(status_code=404, detail="File not found on server.")

    # Process Page by Page
    page_summaries = []
    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
    try:
        if file_path.lower().endswith('.pdf'):
            with pdfplumber.open(file_path) as pdf:
                # LIMIT: Process max 5 pages for demo performance
                for i, page in enumerate(pdf.pages[:5]): 
                    text = page.extract_text() or ""
                    if len(text) < 50: 
                        summary = "No significant text found."
                    else:
                        prompt = f"Summarize this page in 3 bullet points:\n{text[:2000]}"
                        summary = llm.invoke(prompt).content
                    
                    page_summaries.append({"page": i + 1, "summary": summary})
        else:
            return {"error": "Page breakdown currently only supported for PDF files."}
                
        return {"filename": filename, "pages": page_summaries}
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/search")
def search_documents(query: str):
    if not os.path.exists("faiss_index"): return {"answer": "System offline. Please upload a document first."}
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    
    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
    qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=vector_store.as_retriever(), return_source_documents=True)
    response = qa_chain.invoke({"query": query})
    
    # Safe citation handling
    citation = "Source: Unknown"
    if response.get('source_documents'):
        citation = f"Source: Page {response['source_documents'][0].metadata.get('page', 'Unknown')}"
        
    return {"answer": response['result'], "citation": citation}

@app.post("/cross-summary")
def generate_cross_summary(selection: DocumentSelection):
    all_docs = load_json_db("doc_store.json")
    selected_docs = [d for d in all_docs if d['filename'] in selection.filenames]
    
    if not selected_docs: return {"cross_summary": "No matching documents found in selection."}

    combined_text = ""
    for d in selected_docs: combined_text += f"- File: {d['filename']} ({d['category']}): {d.get('summary', '')}\n"
    
    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
    prompt = f"You are an Intelligence Analyst. Write a connection report based ONLY on these documents:\n{combined_text}\nIdentify relationships and combine information."
    
    response = llm.invoke(prompt)
    return {"cross_summary": response.content}


# import os
# import shutil
# import json
# from datetime import datetime, timedelta
# from typing import List, Optional

# from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# from pydantic import BaseModel
# from jose import JWTError, jwt
# from dotenv import load_dotenv

# from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# from langchain.chains import RetrievalQA
# from langchain_community.vectorstores import FAISS
# from ingest import ingest_file  # Expects ingest_file(path, owner)

# load_dotenv()

# app = FastAPI()

# SECRET_KEY = "SECRET_KEY"
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 60
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --- MODELS ---
# class DocumentSelection(BaseModel):
#     filenames: List[str]

# class UserCredentials(BaseModel):
#     username: str
#     password: str

# class User(BaseModel):
#     username: str

# # --- HELPERS ---
# def load_json_db(filename):
#     if not os.path.exists(filename): return []
#     try:
#         with open(filename, "r") as f: return json.load(f)
#     except: return []

# def save_json_db(filename, data):
#     with open(filename, "w") as f: json.dump(data, f, indent=4)

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
#         if username is None: raise credentials_exception
#     except JWTError: raise credentials_exception
    
#     users = load_json_db("users.json")
#     user_data = next((u for u in users if u["username"] == username), None)
#     if user_data is None: raise credentials_exception
#     return User(username=user_data["username"])

# # --- ROUTES ---

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
#         return {"token": create_access_token(data={"sub": user["username"]}), "username": user['username']}
#     else:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

# # --- SECURE DOCUMENT ENDPOINTS ---

# @app.get("/documents")
# def list_documents(current_user: User = Depends(get_current_user)):
#     docs = load_json_db("doc_store.json")
#     # FILTER: Only show docs owned by the logged-in user
#     return [d for d in docs if d.get("owner") == current_user.username]

# @app.post("/upload")
# async def upload_document(
#     file: UploadFile = File(...), 
#     current_user: User = Depends(get_current_user) # Require Login
# ):
#     temp_filename = f"temp_{file.filename}"
#     with open(temp_filename, "wb") as buffer: 
#         shutil.copyfileobj(file.file, buffer)
    
#     # PASS USERNAME TO INGEST (Fixes public file issue)
#     result = ingest_file(temp_filename, current_user.username)
    
#     if os.path.exists(temp_filename): 
#         os.remove(temp_filename)
#     return result

# @app.get("/search")
# def search_documents(query: str):
#     if not os.path.exists("faiss_index"): return {"answer": "System offline. Please upload a document first."}
    
#     embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
#     vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    
#     # STRICTLY KEPT: gemini-flash-latest
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
#     for d in selected_docs: combined_text += f"- File: {d['filename']} ({d['category']}): {d.get('summary', '')}\n"
    
#     # STRICTLY KEPT: gemini-flash-latest
#     llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    
#     prompt = f"You are an Intelligence Analyst. Write a connection report based ONLY on these documents:\n{combined_text}\nIdentify relationships and combine information."
    
#     response = llm.invoke(prompt)
#     return {"cross_summary": response.content}

