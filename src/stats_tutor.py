import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import json
from openai import OpenAI
from mem0 import Memory


class StatsTutor:
    def __init__(self):
        """Initialize the tutor with memory configuration"""
        self.memory = Memory.from_config(
            {
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": "gpt-4o-mini",
                        "temperature": 0,
                        "max_tokens": 2000,
                    },
                }
            }
        )
        self.client = OpenAI()
        self.app_id = "stats-101-tutor"
        self.message_history = []

    def _generate_response(self, messages: List[Any]) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""

    def handle_interaction(self, user_input: str, user_id: str) -> str:
        """
        Generate a response to the user (student) as a tutor would,
        and updates the memory store as a side effect.
        """

        messages = [
            {
                "role": "system",
                "content": "You are a Statistics 101 tutor. Build upon previous explanations using simple, succint language.",
            }
        ]

        if self.message_history:
            messages.extend(self.message_history)

        messages.append({"role": "user", "content": user_input})

        response = self._generate_response(messages)
        self.message_history.append({"role": "user", "content": user_input})
        self.message_history.append({"role": "assistant", "content": response})

        # Something not explicit is that mem0 will take the composite of the existing memory and the new message history
        # and decide whether to add or update the memory.

        self.memory.add(
            self.message_history,
            user_id=user_id,
            app_id=self.app_id,
            metadata={
                "timestamp": datetime.now().isoformat(),
            },
        )

        return response

    def _get_conversation_context(
        self, user_id: str, current_input: str
    ) -> List[Dict[str, str]]:
        """Retrieve relevant context from previous interactions"""
        recent_memories = self.memory.search(
            current_input,
            user_id=user_id,
            limit=5,
            filter_={
                "app_id": self.app_id,
                "type": "interaction",
            },
        )

        context_messages = []
        for memory in recent_memories:
            content = json.loads(memory["text"])
            context_messages.extend(
                [
                    {"role": "user", "content": content["user_input"]},
                    {"role": "assistant", "content": content["tutor_response"]},
                ]
            )

        return context_messages

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
