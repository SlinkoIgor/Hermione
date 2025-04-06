# Hermione Agent API

This is a FastAPI service that provides an HTTP interface to the Hermione agent.

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Set up your environment variables in the `.env` file.

## Running the API

To start the API server, run:

```bash
python api.py
```

The server will start on http://127.0.0.1:8123.

## API Endpoints

### 1. Stream Run

```
POST /runs/stream
```

This endpoint streams the agent's response to a user message.

Example request:

```bash
curl -s --request POST \
    --url "http://127.0.0.1:8123/runs/stream" \
    --header 'Content-Type: application/json' \
    --data '{
        "assistant_id": "optional-id",
        "input": {
            "messages": [
                {
                    "role": "human",
                    "content": "What is LangGraph?"
                }
            ]
        },
        "stream_mode": "updates"
    }'
```

### 2. Run

```
POST /runs
```

This endpoint runs the agent and returns the complete response.

Example request:

```bash
curl -s --request POST \
    --url "http://127.0.0.1:8123/runs" \
    --header 'Content-Type: application/json' \
    --data '{
        "assistant_id": "optional-id",
        "input": {
            "messages": [
                {
                    "role": "human",
                    "content": "What is LangGraph?"
                }
            ]
        },
        "stream_mode": "full"
    }'
```

## API Documentation

Once the server is running, you can access the API documentation at:

- Swagger UI: http://127.0.0.1:8123/docs
- ReDoc: http://127.0.0.1:8123/redoc 