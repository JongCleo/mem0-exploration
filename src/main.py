from stats_tutor import StatsTutor
import time
import uuid
from typing import Optional, List, Any
from dotenv import load_dotenv

load_dotenv()

USER_ID = "user_number_uno"


def learning_mode(tutor: StatsTutor) -> None:
    print("\nEntering learning mode. Type 'exit' to close the session.")

    while True:
        user_input = input("\nUser: ").strip()

        if user_input.lower() == "exit":
            break

        response, metadata = tutor.handle_interaction(
            user_input,
            user_id=USER_ID,
        )

        print("\nTutor:", response)


def testing_mode(tutor: StatsTutor) -> None:
    print("\nEntering testing mode. Type 'exit' to close the session.")

    while True:
        candidates = tutor.get_testing_candidates(USER_ID)

        if not candidates:
            print("\nNo concepts ready for testing right now. Exiting...")
            break

        for candidate in candidates:
            print(f"\nTesting topic: {candidate['context']}")

            question = tutor.generate_test_question(candidate)
            print("\nTest Question:", question)

            print("\nType your answer (or 'skip' to move to next topic):")
            user_answer = input().strip()

            if user_answer.lower() == "skip":
                continue

            result = tutor.evaluate_answer(candidate, user_answer)

            print("\nFeedback:", result["feedback"])
            print("Result:", "Correct! ✓" if result["is_correct"] else "Incorrect ✗")

        print("\nTesting complete. Exiting...")
        break


if __name__ == "__main__":
    tutor = StatsTutor()

    print("Welcome to the Statistics Tutor!")

    mode = ""
    while True:
        mode = input("\nEnter mode (learn/test/quit): ").lower().strip()
        if mode in ["learn", "test", "quit"]:
            break
        else:
            print("Invalid mode. Please enter 'learn', 'test', or 'quit'")

    if mode == "learn":
        learning_mode(tutor)
    else:
        testing_mode(tutor)
