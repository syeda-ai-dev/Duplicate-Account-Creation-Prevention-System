# Face Recognition Fraud Protection System

A FastAPI-based system that uses Face++ API to prevent duplicate account creation by detecting and comparing face images. The system stores face tokens in MongoDB and provides APIs for face verification and duplicate detection.

## Features

- Face detection using Face++ API
- Duplicate face checking across multiple FaceSets
- MongoDB integration for storing face tokens
- Docker and Docker Compose support
- Nginx reverse proxy configuration
- RESTful API endpoints for face verification

## Prerequisites

- Python 3.12+
- MongoDB
- Docker and Docker Compose (optional)
- Face++ API credentials

## Local Development Setup

1. Clone the repository
```sh
git clone < https://github.com/syeda-ai-dev/Duplicate-Account-Creation-Prevention-System.git >
cd Duplicate-Account-Creation-Prevention-System
```
2. Create and activate a virtual environment
```sh
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```
3. Install dependencies
```sh
pip install -r requirements.txt
```
4. Create a .env file with your configurations
```sh
FPP_API_KEY = 'your-api-key'
FPP_API_SECRET = 'your-secret-key'
FPP_CREATE = 'https://api-us.faceplusplus.com/facepp/v3/faceset/create'
FPP_DETECT = 'https://api-us.faceplusplus.com/facepp/v3/detect'
FPP_SEARCH = 'https://api-us.faceplusplus.com/facepp/v3/search'
FPP_ADD = 'https://api-us.faceplusplus.com/facepp/v3/faceset/addface'
FPP_GET_DETAIL = 'https://api-us.faceplusplus.com/facepp/v3/faceset/getdetail'
MONGODB_URI = 'your-mongo-uri'
MONGODB_DB = 'you-db-name'
MONGODB_COLLECTION = 'your-collection-name'
```
5. Run the application locally using Uvicorn
```sh
uvicorn com.mhire.app.main:app --reload
```
The API will be available at ```http://localhost:8000```, with Swagger UI: ```http://localhost:8000/docs```

## Docker Setup

1. Build and run using Docker Compose
```sh
docker-compose up --build -d
```
This will:

- Build the FastAPI application container
- Set up Nginx reverse proxy
- Expose the service on port 8052
- Access the API at ```http://your-ip-address:8052```, with Swagger UI: ```http://your-ip-address:8052/docs```

2. Stop the containers

## API Documentation
Main Endpoint: 
- POST /api/v1/face/verify: Upload and verify a face image
- Returns match confidence and duplicate detection results
- Saves new faces to the database if no duplicates found