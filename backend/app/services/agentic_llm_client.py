"""
Agentic LLM client with tool-calling support for Groq.
"""
import httpx
import json
from typing import Dict, Any, List, Optional, Tuple
import logging

from app.core.settings import settings

logger = logging.getLogger(__name__)


class AgenticLLMClient:
    """LLM client with tool-calling capabilities."""
    
    def __init__(self):
        self.base_url = settings.GROQ_BASE_URL
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL
        self.timeout = 60.0  # Longer timeout for agentic workflows
    
    async def run_agentic_workflow(
        self,
        system_prompt: str,
        user_message: str,
        tools: List[Dict[str, Any]],
        tool_executor,
        max_iterations: int = 15
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
        """
        Run agentic workflow with tool calling.
        
        Args:
            system_prompt: System instructions
            user_message: User's request
            tools: Tool definitions
            tool_executor: Object with execute_tool(name, args) method
            max_iterations: Max tool calling iterations
            
        Returns:
            Tuple of (final_response, conversation_history, error)
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Agentic iteration {iteration}/{max_iterations}")
            
            try:
                # Call LLM
                response = await self._make_request(
                    messages=messages,
                    tools=tools,
                    temperature=0.3
                )
                
                if not response:
                    return None, messages, "LLM returned empty response"
                
                assistant_message = response["choices"][0]["message"]
                messages.append(assistant_message)
                
                # Check if LLM wants to call tools
                tool_calls = assistant_message.get("tool_calls", [])
                
                if not tool_calls:
                    # LLM is done, return final response
                    content = assistant_message.get("content", "")
                    
                    # Try to parse JSON response
                    try:
                        # Remove markdown code blocks if present
                        if content.startswith("```"):
                            lines = content.split("\n")
                            content = "\n".join(lines[1:-1])
                        
                        final_result = json.loads(content.strip())
                        logger.info("Agentic workflow complete")
                        return final_result, messages, None
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse final response: {content[:200]}")
                        return None, messages, "LLM response is not valid JSON"
                
                # Execute tool calls
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    
                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    logger.info(f"Executing tool: {tool_name}")
                    logger.debug(f"Arguments: {arguments}")
                    
                    # Execute tool
                    tool_result = await tool_executor.execute_tool(tool_name, arguments)
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "content": json.dumps(tool_result)
                    })
                
            except Exception as e:
                logger.error(f"Error in agentic iteration: {str(e)}", exc_info=True)
                return None, messages, str(e)
        
        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached")
        return None, messages, "Max iterations reached without completion"
    
    async def _make_request(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Make request to Groq API with retry logic.
        
        Args:
            messages: Conversation messages
            tools: Tool definitions
            temperature: Sampling temperature
            retry_count: Current retry attempt
            max_retries: Maximum retry attempts
            
        Returns:
            API response
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4000
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            # Handle rate limits with retry
            if e.response.status_code == 429 and retry_count < max_retries:
                import asyncio
                import re
                
                # Extract wait time from error message
                error_text = e.response.text
                wait_match = re.search(r'try again in ([\d.]+)s', error_text)
                
                if wait_match:
                    wait_time = float(wait_match.group(1))
                    logger.warning(f"Rate limit hit, waiting {wait_time}s before retry {retry_count + 1}/{max_retries}")
                    await asyncio.sleep(wait_time + 1)  # Add 1s buffer
                else:
                    # Default wait
                    logger.warning(f"Rate limit hit, waiting 25s before retry {retry_count + 1}/{max_retries}")
                    await asyncio.sleep(25)
                
                # Retry
                return await self._make_request(messages, tools, temperature, retry_count + 1, max_retries)
            
            logger.error(f"Groq API error: {e.response.status_code} - {e.response.text}")
            return None
            
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            return None


# Global instance
agentic_llm_client = AgenticLLMClient()