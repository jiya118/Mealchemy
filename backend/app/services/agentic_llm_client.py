"""
Agentic LLM client with tool-calling support for Google Gemini.
"""
import json
import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
import logging

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from google.api_core import exceptions as google_exceptions

from app.core.settings import settings

logger = logging.getLogger(__name__)


def _send_with_retry(chat, message, max_retries=3):
    """Send a message to Gemini with retry logic for rate limits."""
    for attempt in range(max_retries + 1):
        try:
            return chat.send_message(message)
        except google_exceptions.ResourceExhausted as e:
            if attempt < max_retries:
                wait_time = 10 * (attempt + 1)  # 10s, 20s, 30s
                print(f"  Rate limit hit, waiting {wait_time}s (retry {attempt + 1}/{max_retries})")
                logger.warning(f"Gemini rate limit, waiting {wait_time}s (retry {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise


def _build_gemini_tools(openai_tools: List[Dict[str, Any]]) -> List[Tool]:
    """
    Convert OpenAI-format tool definitions to Gemini FunctionDeclaration format.
    
    Args:
        openai_tools: Tool definitions in OpenAI/Groq format
        
    Returns:
        List of Gemini Tool objects
    """
    declarations = []
    
    for tool_def in openai_tools:
        func = tool_def["function"]
        params = func.get("parameters", {})
        
        # Clean parameters: remove 'required' from nested object items
        # and any keys Gemini doesn't support
        cleaned_params = _clean_params_for_gemini(params)
        
        declarations.append(
            FunctionDeclaration(
                name=func["name"],
                description=func["description"],
                parameters=cleaned_params
            )
        )
    
    return [Tool(function_declarations=declarations)]


def _clean_params_for_gemini(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively clean parameter schemas for Gemini compatibility.
    Gemini is stricter than OpenAI about JSON schema features.
    """
    cleaned = {}
    
    for key, value in params.items():
        if key == "default":
            # Gemini doesn't support 'default' in schemas
            continue
        
        if isinstance(value, dict):
            cleaned[key] = _clean_params_for_gemini(value)
        elif isinstance(value, list):
            cleaned[key] = [
                _clean_params_for_gemini(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value
    
    return cleaned


import os

class AgenticLLMClient:
    """LLM client with tool-calling capabilities using Google Gemini."""
    
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY_MEAL_PLANNER)
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    
    async def run_agentic_workflow(
        self,
        system_prompt: str,
        user_message: str,
        tools: List[Dict[str, Any]],
        tool_executor,
        max_iterations: int = 15
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
        """
        Run agentic workflow with Gemini function calling.
        
        Args:
            system_prompt: System instructions
            user_message: User's request
            tools: Tool definitions (OpenAI format — will be converted)
            tool_executor: Object with execute_tool(name, args) method
            max_iterations: Max tool calling iterations
            
        Returns:
            Tuple of (final_response, conversation_history, error)
        """
        # Convert OpenAI-format tools to Gemini format
        gemini_tools = _build_gemini_tools(tools)
        
        # Create model with tools and system instruction
        model = genai.GenerativeModel(
            model_name=self.model_name,
            tools=gemini_tools,
            system_instruction=system_prompt
        )
        
        # Start chat
        chat = model.start_chat()
        
        # Track conversation for debugging
        conversation_log = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        iteration = 0
        
        try:
            # Send initial user message
            print(f"Sending initial message to Gemini ({self.model_name})")
            logger.info(f"Starting Gemini agentic workflow with model {self.model_name}")
            
            response = _send_with_retry(chat, user_message)
            
            while iteration < max_iterations:
                iteration += 1
                print(f"Agentic iteration {iteration}/{max_iterations}")
                logger.info(f"Agentic iteration {iteration}/{max_iterations}")
                
                # Check if response has candidates
                if not response.candidates:
                    print("Gemini returned no candidates")
                    return None, conversation_log, "Gemini returned no candidates"
                
                candidate = response.candidates[0]
                
                # Check for function calls in response parts
                has_function_call = False
                function_responses = []
                
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call') and part.function_call.name:
                        has_function_call = True
                        tool_name = part.function_call.name
                        tool_args = dict(part.function_call.args) if part.function_call.args else {}
                        
                        print(f"  Tool call: {tool_name}({tool_args})")
                        logger.info(f"Executing tool: {tool_name}")
                        logger.debug(f"Arguments: {tool_args}")
                        
                        # Execute the tool
                        try:
                            tool_result = await tool_executor.execute_tool(tool_name, tool_args)
                            print(f"  Tool {tool_name} returned {tool_result.get('found', '?')} items")
                        except Exception as e:
                            logger.error(f"Tool execution failed: {tool_name}: {e}")
                            tool_result = {"error": str(e)}
                        
                        conversation_log.append({
                            "role": "assistant",
                            "tool_call": tool_name,
                            "tool_args": tool_args
                        })
                        conversation_log.append({
                            "role": "tool",
                            "name": tool_name,
                            "content": json.dumps(tool_result)
                        })
                        
                        # Collect function response for batch send
                        function_responses.append(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"result": tool_result}
                                )
                            )
                        )
                
                if has_function_call and function_responses:
                    # Send all function responses back to Gemini
                    response = _send_with_retry(
                        chat,
                        genai.protos.Content(parts=function_responses)
                    )
                    continue
                
                # No function calls — LLM is done, extract text response
                text_content = ""
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_content += part.text
                
                if not text_content:
                    print("Gemini returned empty text response")
                    return None, conversation_log, "Gemini returned empty response"
                
                # Parse JSON from text
                try:
                    # Remove markdown code blocks if present
                    clean = text_content.strip()
                    if clean.startswith("```"):
                        lines = clean.split("\n")
                        clean = "\n".join(lines[1:-1])
                    
                    final_result = json.loads(clean.strip())
                    logger.info("Agentic workflow complete")
                    print(f"Agentic workflow complete after {iteration} iterations")
                    return final_result, conversation_log, None
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse final response: {text_content[:300]}")
                    return None, conversation_log, f"LLM response is not valid JSON: {text_content[:200]}"
        
        except Exception as e:
            logger.error(f"Error in agentic workflow: {str(e)}", exc_info=True)
            print(f"Agentic workflow error: {str(e)}")
            return None, conversation_log, str(e)
        
        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached")
        return None, conversation_log, "Max iterations reached without completion"


# Global instance
agentic_llm_client = AgenticLLMClient()