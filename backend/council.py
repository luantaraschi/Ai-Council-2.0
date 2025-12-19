"""3-stage LLM Council orchestration."""

from typing import List, Dict, Any, Tuple, Optional
import base64
import io
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from llm_client import query_models_parallel, query_model
from config import COUNCIL_MODELS, CHAIRMAN_MODEL


def extract_text_from_pdf(base64_data: str) -> str:
    """Extract text from a base64 encoded PDF."""
    if not PdfReader:
        return "[PDF processing unavailable - pypdf not installed]"
        
    try:
        # Check if data contains header, strip if needed
        if "," in base64_data[:100]:
            base64_data = base64_data.split(",", 1)[1]
            
        pdf_bytes = base64.b64decode(base64_data)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        return f"[Error extracting PDF text: {str(e)}]"


def decode_text_file(base64_data: str) -> str:
    """Decode base64 encoded text file."""
    try:
        if "," in base64_data[:100]:
            base64_data = base64_data.split(",", 1)[1]
        return base64.b64decode(base64_data).decode('utf-8')
    except Exception as e:
        return f"[Error decoding file: {str(e)}]"


def process_message_content(content: str, attachments: List[Dict[str, Any]] = None) -> Any:
    """
    Process message content and attachments into LLM-ready format.
    Handles text extraction from docs and image formatting.
    """
    text_content = content or ""
    image_parts = []
    
    if attachments:
        for att in attachments:
            mime_type = att.get('mimeType', '')
            data = att.get('data', '')
            name = att.get('name', 'file')
            
            if mime_type == 'application/pdf':
                pdf_text = extract_text_from_pdf(data)
                text_content += f"\n\n[Attachment: {name} (PDF Content)]\n{pdf_text}\n[End Attachment]"
                
            elif mime_type.startswith('text/') or mime_type in ['application/json', 'application/javascript', 'application/csv']:
                decoded = decode_text_file(data)
                text_content += f"\n\n[Attachment: {name}]\n{decoded}\n[End Attachment]"
                
            elif mime_type.startswith('image/'):
                # Format for OpenAI (handled by llm_client for Gemini conversion)
                if "," not in data[:100]:
                    data_url = f"data:{mime_type};base64,{data}"
                else:
                    data_url = data # Already has prefix
                    
                image_parts.append({
                    "type": "image_url",
                    "image_url": {"url": data_url}
                })
    
    # If no images, just return text
    if not image_parts:
        return text_content
        
    # If images, return structured content
    final_content = []
    if text_content:
        final_content.append({"type": "text", "text": text_content})
        
    final_content.extend(image_parts)
    return final_content


def build_chat_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert stored history into LLM message format."""
    llm_messages = []
    
    for msg in history:
        role = msg.get('role')
        
        if role == 'user':
            content = msg.get('content', '')
            attachments = msg.get('attachments', [])
            processed = process_message_content(content, attachments)
            llm_messages.append({"role": "user", "content": processed})
            
        elif role == 'assistant':
            # For assistant, we use the final synthesis (Stage 3)
            # If Stage 3 failed or is missing, try fallback
            stage3 = msg.get('stage3', {})
            response = stage3.get('response', '')
            if not response:
                # Fallback to finding any content
                response = "[Error: No response found in history]"
            
            llm_messages.append({"role": "assistant", "content": response})
            
    return llm_messages


async def stage1_collect_responses(
    user_query: str, 
    history: List[Dict[str, Any]], 
    attachments: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.
    """
    # Build history
    messages = build_chat_history(history)
    
    # Add current message
    current_content = process_message_content(user_query, attachments)
    messages.append({"role": "user", "content": current_content})

    # Query all models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    history_context: str = ""
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    context_str = ""
    if history_context:
        context_str = f"\n\nContext from previous conversation:\n{history_context[-2000:]}..." # Limit context size

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}{context_str}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    history: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])
    
    # Build history context
    # Note: For stage 3, we reconstruct the message history naturally so the chairman
    # sees the full conversation flow, then we append the "Council Deliberation" data as a system or user prompt.
    
    messages = build_chat_history(history or [])
    
    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to the user's latest question, and then ranked each other's responses.

User Question: {user_query}

STAGE 1 - Individual Responses from Council Members:
{stage1_text}

STAGE 2 - Peer Rankings and Evaluations:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom. Do not explicitly mention "Stage 1" or "Stage 2" in your final answer unless necessary to explain a conflict. Speak directly to the user."""

    messages.append({"role": "user", "content": chairman_prompt})

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """Generate a short title for a conversation."""
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]
    
    # Use gemini-2.5-flash for title generation
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()
    title = title.strip('"\'')
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(
    user_query: str, 
    history: List[Dict[str, Any]] = None,
    attachments: List[Dict[str, Any]] = None
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.
    """
    history = history or []
    
    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(user_query, history, attachments)

    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect rankings
    # Provide simple context string for ranking
    history_ctx = f"Previous messages: {len(history)}" if history else ""
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results, history_ctx)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        history
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    return stage1_results, stage2_results, stage3_result, metadata
