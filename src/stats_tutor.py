import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import json
from openai import OpenAI
from mem0 import MemoryClient
from pydantic import BaseModel, Field


class TutorResponse(BaseModel):
    response: str = Field(description="The tutor's response to the student")
    reason: str = Field(
        description="Explanation of why this was classified as a learning request or not"
    )
    is_learning_request: bool = Field(
        description="Whether the student is asking to learn or understand a concept"
    )


class EvaluationResponse(BaseModel):
    is_correct: bool = Field(
        description="Whether the student's answer demonstrates understanding"
    )
    feedback: str = Field(
        description="Specific, constructive feedback about the student's answer"
    )


class StatsTutor:
    def __init__(self):
        """Initialize the tutor with memory configuration"""
        self.memory = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.app_id = "stats-101-tutor"
        self.message_history = []

    def handle_interaction(self, user_input: str, user_id: str) -> str:
        """
        Generate a response to the user (student) as a tutor would,
        and updates the memory store as a side effect.
        """
        messages = [
            {
                "role": "system",
                "content": "You are a knowledgeable Statistics 101 tutor helping a student learn statistics concepts. Follow these guidelines:\n\n"
                "1. Use simple, clear language suitable for beginners\n"
                "2. Build upon previous explanations to reinforce learning\n"
                "3. Break down complex concepts into digestible chunks\n"
                "4. Use concrete, real-world examples to illustrate concepts\n"
                "5. Check for understanding by asking reflective questions\n"
                "6. Acknowledge and validate the student's current understanding\n"
                "7. Correct misconceptions gently and constructively\n"
                "8. Focus on core statistical intuition over formulas\n\n"
                "Your goal is to help the student develop a strong foundational understanding of statistics.",
            }
        ]

        if self.message_history:
            messages.extend(self.message_history)

        messages.append({"role": "user", "content": user_input})

        response = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=self.message_history,
            temperature=0,
            response_format=TutorResponse,
        )

        result = response.choices[0].message.parsed

        if not result:
            return ""

        # Update message history with the actual conversation
        self.message_history.append({"role": "user", "content": user_input})
        self.message_history.append({"role": "assistant", "content": result.response})

        # We need a copy because we need to modify the contents solely to tell Mem0 to add it to memory
        if result.is_learning_request:
            memory_messages = self.message_history.copy()
            last_user_msg = memory_messages[-2]["content"]
            memory_messages[-2]["content"] = (
                f"{last_user_msg}\n[IMPORTANT: Student is requesting to learn about this concept]"
            )

            self.memory.add(
                memory_messages,
                user_id=user_id,
                app_id=self.app_id,
                metadata={
                    "timestamp": datetime.now().isoformat(),
                },
            )

        return result.response

    def get_testing_candidates(self, conversation_id: str) -> List[Dict]:
        """Get concepts that are ready for testing based on conversation history"""
        memories = self.memory.search(
            "type:interaction",
            user_id=conversation_id,
            filter_={"app_id": self.app_id},
        )

        # Group by context and find concepts ready for testing
        concepts = {}
        for memory in memories:
            content = json.loads(memory["text"])
            context = content.get("context")
            if not context:
                continue

            if context not in concepts:
                concepts[context] = {
                    "last_tested": None,
                    "interactions": [],
                    "memory_ids": [],
                }

            concepts[context]["interactions"].append(content)
            concepts[context]["memory_ids"].append(memory["id"])

            if content.get("last_tested"):
                concepts[context]["last_tested"] = content["last_tested"]

        # Filter for concepts ready for testing
        testing_candidates = []
        for context, data in concepts.items():
            if self._should_test(data.get("last_tested")):
                testing_candidates.append(
                    {
                        "context": context,
                        "interactions": data["interactions"],
                        "memory_ids": data["memory_ids"],
                    }
                )

        return testing_candidates

    def _should_test(self, last_tested: Optional[str]) -> bool:
        """Determine if a concept should be tested"""
        if not last_tested:
            return True

        last_tested_date = datetime.fromisoformat(last_tested)
        # For now, use a simple 4-hour interval
        return datetime.now() >= last_tested_date + timedelta(hours=4)

    def generate_test_question(self, context: Dict) -> str:
        """Generate a test question based on previous interactions"""
        messages = [
            {
                "role": "system",
                "content": "You are a Statistics 101 tutor creating test questions. "
                "Based on the previous interaction, generate a question that tests "
                "understanding of the concept. Make it specific and practical.",
            }
        ]

        # Add context from previous interactions
        for interaction in context["interactions"]:
            messages.extend(
                [
                    {"role": "user", "content": interaction["user_input"]},
                    {"role": "assistant", "content": interaction["tutor_response"]},
                ]
            )

        messages.append(
            {
                "role": "user",
                "content": "Generate a test question about this concept that requires "
                "understanding, not just memorization.",
            }
        )

        response = self._generate_response(messages)
        return response

    def evaluate_answer(self, context: Dict, user_answer: str) -> Dict[str, Any]:
        """
        Use LLM to evaluate the user's answer and provide feedback.
        Also updates the memory with test results.
        Returns evaluation result containing correctness, feedback, and metadata.
        """
        messages = [
            {
                "role": "system",
                "content": "You are a Statistics 101 tutor evaluating a student's answer. "
                "Determine if they demonstrate understanding. "
                "Provide specific, constructive feedback. "
                "Start your response with either 'CORRECT' or 'INCORRECT' followed by your explanation.",
            }
        ]

        # Add relevant context
        for interaction in context["interactions"][
            -2:
        ]:  # Last 2 interactions for brevity
            messages.extend(
                [
                    {"role": "user", "content": interaction["user_input"]},
                    {"role": "assistant", "content": interaction["tutor_response"]},
                ]
            )

        messages.append(
            {
                "role": "user",
                "content": f"Evaluate this answer: {user_answer}",
            }
        )

        response = self._generate_response(messages)
        is_correct = response.startswith("CORRECT")
        feedback = response.split("\n", 1)[1].strip()  # Remove CORRECT/INCORRECT line

        # Update memory with test results
        timestamp = datetime.now().isoformat()
        for memory_id in context["memory_ids"]:
            memory = self.memory.get(memory_id)
            if not memory:
                continue

            content = json.loads(memory["text"])
            content["last_tested"] = timestamp
            content["test_result"] = {
                "correct": is_correct,
                "feedback": feedback,
                "timestamp": timestamp,
            }

            self.memory.update(memory_id, json.dumps(content))

        return {
            "is_correct": is_correct,
            "feedback": feedback,
            "timestamp": timestamp,
        }
