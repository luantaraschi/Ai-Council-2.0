"""Supabase-based storage for conversations."""

import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import SUPABASE_URL, SUPABASE_KEY


def _get_headers():
    """Get headers for Supabase API requests."""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


def create_conversation(conversation_id: str, user_id: str = "default") -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation
        user_id: User identifier for per-user conversations

    Returns:
        New conversation dict
    """
    conversation = {
        "id": conversation_id,
        "user_id": user_id,
        "title": "New Conversation",
        "messages": [],
        "created_at": datetime.utcnow().isoformat()
    }
    
    response = httpx.post(
        f"{SUPABASE_URL}/rest/v1/conversations",
        headers=_get_headers(),
        json=conversation
    )
    
    if response.status_code == 201:
        data = response.json()
        return data[0] if data else conversation
    else:
        print(f"Error creating conversation: {response.status_code} - {response.text}")
        # Return the conversation anyway for local fallback
        return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    response = httpx.get(
        f"{SUPABASE_URL}/rest/v1/conversations?id=eq.{conversation_id}",
        headers=_get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data:
            return data[0]
    return None


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    response = httpx.patch(
        f"{SUPABASE_URL}/rest/v1/conversations?id=eq.{conversation['id']}",
        headers=_get_headers(),
        json={
            "title": conversation.get("title", "New Conversation"),
            "messages": conversation.get("messages", [])
        }
    )
    
    if response.status_code not in [200, 204]:
        print(f"Error saving conversation: {response.status_code} - {response.text}")


def list_conversations(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List conversations (metadata only), optionally filtered by user_id.

    Args:
        user_id: Optional user ID to filter conversations

    Returns:
        List of conversation metadata dicts
    """
    url = f"{SUPABASE_URL}/rest/v1/conversations?select=id,user_id,title,messages,created_at&order=created_at.desc"
    
    if user_id:
        url += f"&user_id=eq.{user_id}"
    
    response = httpx.get(url, headers=_get_headers())
    
    if response.status_code == 200:
        data = response.json()
        # Convert to metadata format
        return [
            {
                "id": conv["id"],
                "user_id": conv.get("user_id", "default"),
                "created_at": conv["created_at"],
                "title": conv.get("title", "New Conversation"),
                "message_count": len(conv.get("messages", []))
            }
            for conv in data
        ]
    
    print(f"Error listing conversations: {response.status_code} - {response.text}")
    return []


def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a conversation.

    Args:
        conversation_id: Conversation identifier

    Returns:
        True if deleted, False if not found
    """
    response = httpx.delete(
        f"{SUPABASE_URL}/rest/v1/conversations?id=eq.{conversation_id}",
        headers=_get_headers()
    )
    
    return response.status_code in [200, 204]


def add_user_message(conversation_id: str, content: str, attachments: List[Dict[str, Any]] = None):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
        attachments: Optional list of attachments
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    messages = conversation.get("messages", [])
    
    message = {
        "role": "user",
        "content": content
    }
    
    if attachments:
        message["attachments"] = attachments
        
    messages.append(message)
    
    conversation["messages"] = messages
    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    messages = conversation.get("messages", [])
    messages.append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })
    
    conversation["messages"] = messages
    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    response = httpx.patch(
        f"{SUPABASE_URL}/rest/v1/conversations?id=eq.{conversation_id}",
        headers=_get_headers(),
        json={"title": title}
    )
    
    if response.status_code not in [200, 204]:
        print(f"Error updating title: {response.status_code} - {response.text}")
