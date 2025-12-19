"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio

import supabase_storage as storage
from council import run_full_council, generate_conversation_title

app = FastAPI(title="LLM Council API")

# Enable CORS for local development and external access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    user_id: str = "default"


class Attachment(BaseModel):
    """File attachment model."""
    name: str
    type: str  # 'image', 'document'
    mimeType: str
    size: int
    data: str  # base64 encoded content


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    attachments: List[Attachment] = []


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    user_id: str = "default"
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(user_id: str = None):
    """List conversations (metadata only), optionally filtered by user_id."""
    return storage.list_conversations(user_id)


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, request.user_id)
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    deleted = storage.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted"}


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists and get history
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    history = conversation.get("messages", [])
    is_first_message = len(history) == 0

    # Add user message to storage
    # Convert Pydantic models to dicts
    attachments_dict = [att.dict() for att in request.attachments] if request.attachments else None
    storage.add_user_message(conversation_id, request.content, attachments_dict)

    # If this is the first message, generate a title
    if is_first_message:
        # We can extract text from attachments if content is empty (e.g. just sending a PDF)
        # But generate_conversation_title expects string.
        title_content = request.content
        if not title_content and request.attachments:
            title_content = f"Analysis of {request.attachments[0].name}"
            
        title = await generate_conversation_title(title_content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content,
        history,
        attachments_dict
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists and get history
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    history = conversation.get("messages", [])
    is_first_message = len(history) == 0
    
    # Convert Pydantic models to dicts
    attachments_dict = [att.dict() for att in request.attachments] if request.attachments else None

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content, attachments_dict)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_content = request.content
                if not title_content and request.attachments:
                    title_content = f"Analysis of {request.attachments[0].name}"
                title_task = asyncio.create_task(generate_conversation_title(title_content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await call_stage1_wrapper(request.content, history, attachments_dict)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            # Import here to avoid circular dependencies if any (none expected but safer)
            from council import stage2_collect_rankings, calculate_aggregate_rankings
            
            history_ctx = f"Previous messages: {len(history)}" if history else ""
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results, history_ctx)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            from council import stage3_synthesize_final
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results, history)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                try:
                    title = await title_task
                    storage.update_conversation_title(conversation_id, title)
                    yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"
                except Exception as e:
                    print(f"Title generation failed: {e}")

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# Wrapper to avoid async issues with direct import in generator
async def call_stage1_wrapper(content, history, attachments):
    from council import stage1_collect_responses
    return await stage1_collect_responses(content, history, attachments)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
