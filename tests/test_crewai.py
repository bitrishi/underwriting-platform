import unittest

from src.exercises.week4_day3_comparison import run_comparison, run_langgraph
from src.exercises.week4_day3_crewai import run_crew


class TestCrewAIExercise(unittest.TestCase):
    def test_run_crew_has_expected_sections(self):
        result = run_crew(print_output=False)
        self.assertIn("task_1", result)
        self.assertIn("task_2", result)
        self.assertIn("run_mode", result)

    def test_run_crew_data_shape(self):
        result = run_crew(print_output=False)
        task_1 = result["task_1"]
        task_2 = result["task_2"]
        if isinstance(task_1, dict):
            self.assertIn("borrower", task_1)
            self.assertIn("credit", task_1)
        if isinstance(task_2, dict):
            self.assertIn("recommendation", task_2)

    def test_langgraph_flow(self):
        result = run_langgraph()
        self.assertIn("borrower", result)
        self.assertIn("credit", result)
        self.assertIn("risk", result)
        self.assertIn("recommendation", result["risk"])

    def test_comparison_summary(self):
        summary = run_comparison()
        self.assertIn("crewai", summary)
        self.assertIn("langgraph", summary)
        self.assertIn("observation", summary)
        self.assertIn("easier_to_write", summary["observation"])
        self.assertIn("more_structured_output", summary["observation"])


if __name__ == "__main__":
    unittest.main()
