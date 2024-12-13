import logging
from stats_tutor import StatsTutor
from dotenv import load_dotenv
from logger_config import setup_logger

load_dotenv()
setup_logger()
logger = logging.getLogger(__name__)

USER_ID = "user_number_uno"


def learning_mode(tutor: StatsTutor) -> None:
    logger.info("Entering learning mode")
    print("\nEntering learning mode. Type 'exit' to close the session.")

    while True:
        user_input = input("\nUser: ").strip()

        if user_input.lower() == "exit":
            logger.info("User exited learning mode")
            break

        logger.info("Processing user input in learning mode")
        response = tutor.handle_interaction(
            user_input,
            user_id=USER_ID,
        )

        print("\nTutor:", response)


def testing_mode(tutor: StatsTutor) -> None:
    logger.info("Entering testing mode")
    print("\nEntering testing mode. Type 'exit' to close the session.")

    while True:
        candidates = tutor.get_testing_candidates(USER_ID)

        if not candidates:
            logger.info("No testing candidates found")
            print("\nNo concepts ready for testing right now. Exiting...")
            break

        for candidate in candidates:
            logger.info(f"Testing candidate concept: {candidate['id']}")
            print(f"\nTesting topic: {candidate['memory']}")

            question = tutor.generate_test_question(candidate)
            print("\nTest Question:", question)

            print("\nType your answer (or 'skip' to move to next topic):")
            user_answer = input().strip()

            if user_answer.lower() == "skip":
                logger.info(f"User skipped question for concept: {candidate['id']}")
                continue

            logger.info(f"Evaluating user answer for concept: {candidate['id']}")
            result = tutor.evaluate_answer(
                memory_id=candidate["id"], user_answer=user_answer
            )

            print("\nFeedback:", result["feedback"])
            print("Result:", "Correct! ✓" if result["is_correct"] else "Incorrect ✗")

        logger.info("Testing mode completed")
        print("\nTesting complete. Exiting...")
        break


if __name__ == "__main__":
    logger.info("Starting Statistics Tutor application")
    tutor = StatsTutor()

    print("Welcome to the Statistics Tutor!")

    mode = ""
    while True:
        mode = input("\nEnter mode (learn/test/quit): ").lower().strip()
        if mode in ["learn", "test", "quit"]:
            logger.info(f"Selected mode: {mode}")
            break
        else:
            logger.warning(f"Invalid mode entered: {mode}")
            print("Invalid mode. Please enter 'learn', 'test', or 'quit'")

    if mode == "learn":
        learning_mode(tutor)
    elif mode == "test":
        testing_mode(tutor)
    else:
        logger.info("Application terminated by user")
