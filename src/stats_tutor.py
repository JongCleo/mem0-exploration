import os
import logging
from datetime import datetime
from typing import List, Dict, Any
import json
from openai import OpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from mem0 import MemoryClient
from pydantic import BaseModel, Field
from test_tracker import TestTracker
from logger_config import setup_logger

setup_logger()
logger = logging.getLogger(__name__)


class TutorResponse(BaseModel):
    response: str = Field(description="The tutor's response to the student")
    reason: str = Field(
        description="Explanation of why this was classified as a testable topic or not"
    )
    is_testable_topic: bool = Field(
        description="Whether the subject of the conversation is a testable topic in a standard statistics course"
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
        self.message_history: List[ChatCompletionMessageParam] = []
        self.test_tracker = TestTracker()

    def handle_interaction(self, user_input: str, user_id: str) -> str:
        """
        Generate a response to the user (student) as a tutor would,
        and updates the memory store as a side effect.
        """
        logger.info(f"Processing user input: {user_input[:50]}...")

        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    "You are a knowledgeable Statistics 101 tutor helping a student learn statistics concepts. "
                    "Follow these guidelines:\n\n"
                    "1. Use simple, clear language suitable for beginners\n"
                    "2. Build upon previous explanations to reinforce learning\n"
                    "3. Break down complex concepts into digestible chunks\n"
                    "4. Use concrete, real-world examples to illustrate concepts\n"
                    "5. Check for understanding by asking reflective questions\n"
                    "6. Acknowledge and validate the student's current understanding\n"
                    "7. Correct misconceptions gently and constructively\n"
                    "8. Focus on core statistical intuition over formulas\n\n"
                    "Your goal is to help the student develop a strong foundational understanding of statistics."
                ),
            }
        ]

        if self.message_history:
            messages.extend(self.message_history)

        messages.append({"role": "user", "content": user_input})

        logger.debug(
            "Sending request to OpenAI with messages (truncated): %s",
            json.dumps(messages[-2:], indent=2),
        )

        response = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,
            response_format=TutorResponse,
        )

        result = response.choices[0].message.parsed

        if not result:
            logger.warning("Received empty response from OpenAI")
            return ""

        logger.debug(
            "Received response from OpenAI: %s",
            json.dumps(result.model_dump(), indent=2),
        )

        # Update message history
        self.message_history.append({"role": "user", "content": user_input})
        self.message_history.append({"role": "assistant", "content": result.response})

        # We need a copy because we need to modify the contents solely to tell Mem0 to add it to memory
        if result.is_testable_topic:
            logger.info("Identified testable topic - storing in memory")
            # Copy and modify messages for memory storage
            memory_messages = [
                {"role": msg["role"], "content": msg.get("content", "")}
                for msg in self.message_history
            ]
            last_user_msg = memory_messages[-2]["content"]
            memory_messages[-2]["content"] = (
                f"{last_user_msg}\n[IMPORTANT: this is a testable topic and should be remembered]"
            )

            self.memory.add(
                messages=memory_messages,
                user_id=user_id,
                app_id=self.app_id,
                metadata={
                    "timestamp": datetime.now().isoformat(),
                },
            )

        return result.response

    def get_testing_candidates(self, user_id: str) -> List[Dict]:
        """Get concepts that are ready for testing based on conversation history"""

        memories = self.memory.get_all(
            filters={"user_id": user_id},
            version="v2",
        )
        logger.debug("Retrieved memories: %s", json.dumps(memories, indent=2))

        candidates = [
            memory
            for memory in memories
            if self.test_tracker.is_ready_for_test(memory["id"])
        ]
        logger.info(f"Found {len(candidates)} testing candidates")
        return candidates

    def generate_test_question(self, candidate: Dict) -> str:
        """Generate a test question based on previous interactions"""

        logger.debug("Using candidate: %s", json.dumps(candidate, indent=2))

        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    "You are a Statistics 101 tutor creating test questions. "
                    "Based on the previous interaction, generate a question that tests "
                    "understanding of the concept. Make it specific and practical."
                ),
            },
            {
                "role": "user",
                "content": f"Here's the concept to generate a question about:\n{candidate['memory']}",
            },
        ]

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,
        )

        question = response.choices[0].message.content or ""
        logger.debug("Generated question: %s", question)

        self.message_history = messages
        self.message_history.append({"role": "assistant", "content": question})

        return question

    def evaluate_answer(self, memory_id: str, user_answer: str) -> Dict[str, Any]:
        logger.info(f"Evaluating answer for memory_id: {memory_id}")
        logger.debug(f"User answer: {user_answer}")

        self.message_history.extend(
            [
                {
                    "role": "system",
                    "content": "Ignore the previous system prompt. Updated Mission: Evaluate the answer given the conversation history and provide structured feedback.",
                },
                {
                    "role": "user",
                    "content": user_answer,
                },
            ]
        )
        response = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=self.message_history,
            response_format=EvaluationResponse,
            temperature=0,
        )

        result = response.choices[0].message.parsed

        if not result:
            logger.warning("Received invalid evaluation response")
            return {
                "is_correct": False,
                "feedback": "The tutor's response was not valid.",
            }
        logger.debug(
            "Received evaluation response: %s",
            json.dumps(result.model_dump(), indent=2),
        )
        self.test_tracker.record_test(memory_id, result.is_correct)
        logger.info(
            f"Recorded test result for memory_id {memory_id}: {'correct' if result.is_correct else 'incorrect'}"
        )

        return {
            "is_correct": result.is_correct,
            "feedback": result.feedback,
        }
