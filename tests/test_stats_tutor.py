import pytest
from datetime import datetime, timedelta
import json
from unittest.mock import Mock, patch
from src.stats_tutor import StatsTutor


@pytest.fixture
def mock_memory():
    return Mock()


@pytest.fixture
def mock_openai():
    return Mock()


@pytest.fixture
def tutor(mock_memory, mock_openai):
    with (
        patch("src.stats_tutor.Memory") as memory_mock,
        patch("src.stats_tutor.OpenAI") as openai_mock,
    ):
        memory_mock.from_config.return_value = mock_memory
        openai_mock.return_value = mock_openai
        return StatsTutor()


def test_conversation_flow(tutor, mock_memory, mock_openai):
    conversation_id = "test-convo-1"

    # Mock OpenAI responses
    mock_openai.chat.completions.create.side_effect = [
        Mock(choices=[Mock(message=Mock(content="Let me explain mean vs median..."))]),
        Mock(choices=[Mock(message=Mock(content="To clarify about median..."))]),
        Mock(choices=[Mock(message=Mock(content="The standard deviation is..."))]),
    ]

    # Simulate conversation history
    conversation = [
        {
            "input": "What's the difference between mean and median?",
            "context": "mean vs median",
        },
        {
            "input": "I'm still confused about median",
            "context": "mean vs median",
        },
        {
            "input": "What is standard deviation?",
            "context": "standard deviation",
        },
    ]

    # Process each interaction
    memory_ids = []
    for interaction in conversation:
        response, metadata = tutor.handle_interaction(
            interaction["input"], conversation_id, interaction["context"]
        )
        memory_ids.append(metadata["memory_id"])

    # Verify memory storage
    assert mock_memory.add.call_count == 3

    # Test duplicate detection
    mock_memory.search.return_value = [
        {
            "id": "1",
            "text": json.dumps(
                {
                    "user_input": "What's the difference between mean and median?",
                    "tutor_response": "Let me explain mean vs median...",
                    "context": "mean vs median",
                    "timestamp": datetime.now().isoformat(),
                }
            ),
        }
    ]

    # Verify that similar questions get context from previous interactions
    response, metadata = tutor.handle_interaction(
        "Can you explain mean and median again?", conversation_id
    )

    # Check that previous context was used
    assert mock_memory.search.called

    # Test testing flow
    mock_memory.search.return_value = [
        {
            "id": "1",
            "text": json.dumps(
                {
                    "user_input": "What's the difference between mean and median?",
                    "tutor_response": "Let me explain mean vs median...",
                    "context": "mean vs median",
                    "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(),
                }
            ),
        }
    ]

    candidates = tutor.get_testing_candidates(conversation_id)
    assert len(candidates) > 0
    assert candidates[0]["context"] == "mean vs median"

    # Test updating test results
    tutor.update_test_result(memory_ids, True, "I understand it now")
    assert mock_memory.update.call_count == len(memory_ids)


def test_spaced_repetition(tutor):
    # Test that concepts are suggested for testing at appropriate intervals
    recent_time = datetime.now() - timedelta(hours=2)
    old_time = datetime.now() - timedelta(hours=6)

    assert not tutor._should_test(recent_time.isoformat())
    assert tutor._should_test(old_time.isoformat())
    assert tutor._should_test(None)


def test_test_question_generation(tutor, mock_openai):
    # Mock context with previous interactions
    context = {
        "interactions": [
            {
                "user_input": "What's the difference between mean and median?",
                "tutor_response": "The mean is the average of all values, while the median is the middle value...",
            },
            {
                "user_input": "Can you give an example?",
                "tutor_response": "Sure! Consider these numbers: 1, 2, 2, 3, 10...",
            },
        ]
    }

    # Mock LLM response for question generation
    mock_openai.chat.completions.create.return_value = Mock(
        choices=[
            Mock(
                message=Mock(
                    content="Given the dataset [1, 2, 2, 3, 10], explain why the median might be a better measure of central tendency than the mean."
                )
            )
        ]
    )

    question = tutor.generate_test_question(context)
    assert "median might be a better measure" in question
    assert mock_openai.chat.completions.create.called


def test_answer_evaluation(tutor, mock_openai, mock_memory):
    # Mock context
    context = {
        "interactions": [
            {
                "user_input": "What's the difference between mean and median?",
                "tutor_response": "The mean is the average of all values...",
            }
        ],
        "memory_ids": ["test_memory_1", "test_memory_2"],
    }

    # Mock memory.get responses
    mock_memory.get.return_value = {
        "text": json.dumps(
            {
                "user_input": "What's the difference between mean and median?",
                "tutor_response": "The mean is the average of all values...",
            }
        )
    }

    # Test correct answer
    mock_openai.chat.completions.create.return_value = Mock(
        choices=[
            Mock(
                message=Mock(
                    content="CORRECT\nExcellent explanation! You clearly understand that..."
                )
            )
        ]
    )

    result = tutor.evaluate_answer(
        context, "The median is better because it's not affected by extreme values"
    )

    assert result["is_correct"]
    assert "Excellent explanation" in result["feedback"]
    assert "timestamp" in result
    assert mock_memory.update.call_count == len(context["memory_ids"])

    # Reset mock counts
    mock_memory.update.reset_mock()

    # Test incorrect answer
    mock_openai.chat.completions.create.return_value = Mock(
        choices=[
            Mock(
                message=Mock(
                    content="INCORRECT\nYour answer shows some confusion about..."
                )
            )
        ]
    )

    result = tutor.evaluate_answer(context, "Mean and median are the same thing")

    assert not result["is_correct"]
    assert "confusion" in result["feedback"]
    assert "timestamp" in result
    assert mock_memory.update.call_count == len(context["memory_ids"])
