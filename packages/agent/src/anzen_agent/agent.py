"""
Anzen AI Agent

AI workflow agent with safety guardrails integration.
Implements a 2-step workflow: (1) plan → (2) execute with external APIs.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException

# Try to import OpenAI, handle if not available
try:
    import openai

    OPENAI_AVAILABLE = True
except Exception as e:
    OPENAI_AVAILABLE = False

    # Mock OpenAI client
    class MockOpenAI:
        def __init__(self, api_key):
            pass

        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    class MockResponse:
                        choices = [
                            type(
                                "obj",
                                (object,),
                                {
                                    "message": type(
                                        "obj", (object,), {"content": "Mock response"}
                                    )()
                                },
                            )
                        ]

                    return MockResponse()

    openai = type("module", (), {"OpenAI": MockOpenAI})()

from .models import AgentRequest, AgentResponse, TaskPlan, TaskStep
from .safety_client import SafetyClient
from .tools import WeatherTool, WikipediaTool

logger = logging.getLogger(__name__)


class AnzenAgent:
    """Anzen AI Agent main class implementing Plan → Execute workflow."""

    def __init__(
        self,
        gateway_url: str,
        openai_api_key: str,
        gateway_api_key: Optional[str] = None,
    ):
        self.gateway_url = gateway_url
        self.openai_api_key = openai_api_key
        self.gateway_api_key = gateway_api_key
        self.router = APIRouter()

        # Initialize components
        self.safety_client = SafetyClient(gateway_url, gateway_api_key)

        # Initialize OpenAI client with error handling
        try:
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
            logger.info("OpenAI client initialized")
        except Exception as e:
            logger.warning(f"OpenAI client initialization failed: {e}, using mock")
            self.openai_client = openai.OpenAI(api_key="mock")

        # Initialize tools with error handling
        try:
            self.wikipedia_tool = WikipediaTool()
            self.weather_tool = WeatherTool()
            logger.info("External tools initialized")
        except Exception as e:
            logger.warning(f"Tools initialization failed: {e}")
            self.wikipedia_tool = None
            self.weather_tool = None

        self._setup_routes()

    async def _safety_check_input(
        self, text: str, route: str = "private:agent"
    ) -> Dict[str, Any]:
        """Check input text for safety issues."""
        try:
            result = await self.safety_client.check_input(text, route)
            return {
                "safe": result["decision"] in ["ALLOW", "REDACT"],
                "decision": result["decision"],
                "safe_text": result["safe_text"],
                "entities": result["entities"],
                "risk_level": result["risk_level"],
                "trace_id": result.get("trace_id"),
            }
        except Exception as e:
            logger.error(f"Safety check failed: {e}")
            return {
                "safe": True,
                "decision": "ALLOW",
                "safe_text": text,
                "entities": [],
                "risk_level": "low",
            }

    async def _safety_check_output(
        self, text: str, route: str = "private:agent"
    ) -> Dict[str, Any]:
        """Check output text for safety issues."""
        try:
            result = await self.safety_client.check_output(text, route)
            return {
                "safe": True,  # Outputs are always made safe through redaction
                "decision": result["decision"],
                "safe_text": result["safe_text"],
                "entities": result["entities"],
                "risk_level": result["risk_level"],
                "trace_id": result.get("trace_id"),
            }
        except Exception as e:
            logger.error(f"Output safety check failed: {e}")
            return {
                "safe": True,
                "decision": "ALLOW",
                "safe_text": text,
                "entities": [],
                "risk_level": "low",
            }

    async def _generate_plan(self, prompt: str) -> TaskPlan:
        """Generate a task plan using OpenAI (Step 1: Plan)."""
        try:
            planning_prompt = f"""
You are a helpful AI assistant that creates task plans. Given a user request, create a step-by-step plan.

Available tools:
- Wikipedia: Search for factual information
- Weather: Get current weather for locations

User request: {prompt}

Create a JSON plan with this structure:
{{
    "steps": [
        {{"step": 1, "action": "search_wikipedia", "description": "Search for information about X"}},
        {{"step": 2, "action": "get_weather", "description": "Get weather for location Y"}},
        {{"step": 3, "action": "synthesize", "description": "Combine information and provide response"}}
    ],
    "estimated_time": 30,
    "complexity": "low"
}}

Only include steps that are needed. Use "search_wikipedia" for factual info, "get_weather" for weather, and "synthesize" to combine results.
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": planning_prompt}],
                temperature=0.1,
            )

            plan_json = json.loads(response.choices[0].message.content)

            steps = [
                TaskStep(
                    step=step["step"],
                    action=step["action"],
                    description=step["description"],
                    status="pending",
                )
                for step in plan_json["steps"]
            ]

            return TaskPlan(
                steps=steps,
                estimated_time=plan_json.get("estimated_time", 30),
                complexity=plan_json.get("complexity", "low"),
            )

        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            # Fallback plan
            return TaskPlan(
                steps=[
                    TaskStep(
                        step=1,
                        action="synthesize",
                        description="Process the request directly",
                        status="pending",
                    )
                ],
                estimated_time=15,
                complexity="low",
            )

    async def _execute_plan(self, plan: TaskPlan, original_prompt: str) -> str:
        """Execute the task plan (Step 2: Execute)."""
        results = []

        for step in plan.steps:
            try:
                step.status = "running"
                logger.info(f"Executing step {step.step}: {step.action}")

                if step.action == "search_wikipedia":
                    # Extract search query from description or use original prompt
                    query = self._extract_search_query(
                        step.description, original_prompt
                    )
                    result = await self.wikipedia_tool.search(query)
                    step.result = result
                    results.append(f"Wikipedia search: {result}")

                elif step.action == "get_weather":
                    # Extract location from description or prompt
                    location = self._extract_location(step.description, original_prompt)
                    result = await self.weather_tool.get_weather(location)
                    step.result = result
                    results.append(f"Weather info: {result}")

                elif step.action == "synthesize":
                    # Synthesize all collected information
                    synthesis_prompt = f"""
Based on the user's request: "{original_prompt}"

Available information:
{chr(10).join(results)}

Provide a helpful, comprehensive response that addresses the user's request using the available information.
"""

                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": synthesis_prompt}],
                        temperature=0.3,
                    )

                    result = response.choices[0].message.content
                    step.result = result
                    results.append(result)

                step.status = "completed"

            except Exception as e:
                logger.error(f"Step {step.step} failed: {e}")
                step.status = "failed"
                step.result = f"Failed: {str(e)}"

        # Return the final synthesis or last result
        final_results = [
            step.result
            for step in plan.steps
            if step.result and step.action == "synthesize"
        ]
        if final_results:
            return final_results[-1]
        else:
            # If no synthesis step, combine all results
            return "\n\n".join([r for r in results if r])

    def _extract_search_query(self, description: str, prompt: str) -> str:
        """Extract search query from step description or prompt."""
        # Simple extraction - in production, use more sophisticated NLP
        if "about" in description.lower():
            return description.split("about")[-1].strip()
        return prompt[:100]  # Fallback to first 100 chars of prompt

    def _extract_location(self, description: str, prompt: str) -> str:
        """Extract location from step description or prompt."""
        # Simple extraction - in production, use NER
        words = (description + " " + prompt).split()
        # Look for common location indicators
        for i, word in enumerate(words):
            if word.lower() in ["in", "at", "for"] and i + 1 < len(words):
                return words[i + 1]
        return "London"  # Default fallback

    def _setup_routes(self):
        """Setup API routes."""

        @self.router.get("/test")
        async def test_endpoint():
            """Simple test endpoint for debugging browser connectivity."""
            logger.info("Test endpoint called from browser")
            return {
                "message": "Agent is reachable from browser!",
                "timestamp": "2025-09-07",
            }

        @self.router.options("/agents/secure")
        async def options_secure_agent():
            """Handle preflight OPTIONS request."""
            logger.info("OPTIONS request received for /agents/secure")
            return {"message": "OK"}

        @self.router.post("/agents/secure", response_model=AgentResponse)
        async def secure_agent(request: AgentRequest):
            """Secure agent interaction with Plan → Execute workflow and safety checks."""
            trace_id = str(uuid.uuid4())

            try:
                logger.info(f"Processing agent request - trace_id: {trace_id}")

                # Step 0: Safety check input
                input_safety = await self._safety_check_input(request.prompt)

                if not input_safety["safe"]:
                    return AgentResponse(
                        response="I cannot process this request as it contains sensitive information that violates our privacy policy.",
                        trace_id=trace_id,
                        safety_checks={"input_safety": input_safety, "blocked": True},
                    )

                # Use the safe version of the prompt
                safe_prompt = input_safety["safe_text"]

                # Step 1: Generate plan (planning phase)
                plan = await self._generate_plan(safe_prompt)
                logger.info(f"Generated plan with {len(plan.steps)} steps")

                # Step 2: Execute plan (execution phase)
                raw_response = await self._execute_plan(plan, safe_prompt)

                # Step 3: Safety check output
                output_safety = await self._safety_check_output(raw_response)
                safe_response = output_safety["safe_text"]

                response = AgentResponse(
                    response=safe_response,
                    plan=plan,
                    trace_id=trace_id,
                    safety_checks={
                        "input_safety": input_safety,
                        "output_safety": output_safety,
                        "blocked": False,
                    },
                )

                logger.info(f"Agent request completed - trace_id: {trace_id}")
                return response

            except Exception as e:
                logger.error(f"Agent request failed - trace_id: {trace_id}, error: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Agent processing failed: {str(e)}"
                )

        @self.router.get("/reports")
        async def get_reports():
            """Get compliance reports."""
            # TODO: Implement actual reporting from database
            return {
                "reports": [
                    {
                        "id": "report-1",
                        "date": "2024-01-15",
                        "total_requests": 150,
                        "blocked_requests": 5,
                        "redacted_requests": 23,
                        "pii_types_detected": [
                            "EMAIL_ADDRESS",
                            "PHONE_NUMBER",
                            "PERSON",
                        ],
                    }
                ],
                "total": 1,
                "summary": {
                    "total_requests": 150,
                    "block_rate": 0.033,
                    "redaction_rate": 0.153,
                    "most_common_pii": "EMAIL_ADDRESS",
                },
            }
