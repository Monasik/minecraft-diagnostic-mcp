import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.analyzers.log_analyzer import analyze_log_records


class LogAnalyzerTests(unittest.TestCase):
    def test_analyze_log_records_emits_startup_and_dependency_findings(self) -> None:
        records = [
            {
                "start_line": 1,
                "text": "[12:00:01 ERROR]: Could not load plugin FancyPlugin v1.0",
                "level": "ERROR",
                "lines": ["[12:00:01 ERROR]: Could not load plugin FancyPlugin v1.0"],
                "has_stacktrace": False,
            },
            {
                "start_line": 2,
                "text": "java.lang.NoClassDefFoundError: com/example/MissingThing\nCaused by: java.lang.ClassNotFoundException: com/example/MissingThing",
                "level": "ERROR",
                "lines": [],
                "has_stacktrace": True,
            },
        ]

        findings = analyze_log_records(records)
        categories = {finding.category for finding in findings}
        source_types = {finding.source_type for finding in findings}

        self.assertIn("plugin_startup", categories)
        self.assertIn("missing_dependency", categories)
        self.assertIn("exception_chain", categories)
        self.assertEqual(source_types, {"log"})
        startup_finding = next(finding for finding in findings if finding.category == "plugin_startup")
        self.assertEqual(startup_finding.context["plugin_name"], "FancyPlugin")
        self.assertEqual(startup_finding.context["line_number"], 1)
        self.assertEqual(startup_finding.context["source"], "docker_logs")

    def test_analyze_log_records_classifies_operational_and_performance_warnings(self) -> None:
        records = [
            {
                "start_line": 10,
                "text": "[22:28:48] [Server thread/WARN]: Brumiiczekk moved too quickly! -1,2,3",
                "level": "WARN",
                "lines": [],
                "has_stacktrace": False,
            },
            {
                "start_line": 11,
                "text": "[22:36:06] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2638ms or 52 ticks behind",
                "level": "WARN",
                "lines": [],
                "has_stacktrace": False,
            },
            {
                "start_line": 12,
                "text": "[22:36:50] [Paper Async Task Handler Thread - 0/WARN]: [spark] A command execution has not completed after 5 seconds, it *might* be stuck.",
                "level": "WARN",
                "lines": [],
                "has_stacktrace": False,
            },
        ]

        findings = analyze_log_records(records)
        categories = [finding.category for finding in findings]

        self.assertIn("operational_movement_warning", categories)
        self.assertIn("performance_warning", categories)
        self.assertIn("monitoring_warning", categories)

        movement = next(finding for finding in findings if finding.category == "operational_movement_warning")
        performance = next(finding for finding in findings if finding.category == "performance_warning")
        monitoring = next(finding for finding in findings if finding.category == "monitoring_warning")

        self.assertEqual(movement.severity, "info")
        self.assertEqual(performance.severity, "warning")
        self.assertEqual(monitoring.severity, "info")
        self.assertLess(movement.priority, performance.priority)

    def test_analyze_log_records_classifies_startup_security_and_compatibility_warnings(self) -> None:
        records = [
            {
                "start_line": 100,
                "text": '[21:33:41] [Server thread/WARN]: **** SERVER IS RUNNING IN OFFLINE/INSECURE MODE!',
                "level": "WARN",
                "lines": [],
                "has_stacktrace": False,
                "startup_phase": True,
            },
            {
                "start_line": 101,
                "text": "[21:33:30] [Server thread/WARN]: [DeluxeMenus] Could not setup a NMS hook for your server version!",
                "level": "WARN",
                "lines": [],
                "has_stacktrace": False,
                "startup_phase": True,
            },
            {
                "start_line": 102,
                "text": "[21:34:08] [Server thread/WARN]: [DeluxeMenus] This option is deprecated and will be removed soon.",
                "level": "WARN",
                "lines": [],
                "has_stacktrace": False,
                "startup_phase": True,
            },
        ]

        findings = analyze_log_records(records)
        categories = [finding.category for finding in findings]

        self.assertIn("startup_security_warning", categories)
        self.assertIn("plugin_compatibility_warning", categories)
        self.assertIn("startup_warning", categories)

        security = next(finding for finding in findings if finding.category == "startup_security_warning")
        compatibility = next(finding for finding in findings if finding.category == "plugin_compatibility_warning")

        self.assertEqual(security.severity, "warning")
        self.assertEqual(compatibility.context["plugin_name"], "DeluxeMenus")
        self.assertGreater(security.priority, 50)
        self.assertGreater(compatibility.priority, 40)


if __name__ == "__main__":
    unittest.main()
