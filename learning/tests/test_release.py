"""State-machine regression tests. No Docker, Kubernetes or network required."""
import copy
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        previous = os.getcwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, previous)
        Path("reports").mkdir()
        self.good = {s: "good-" + s for s in release.SERVICES}
        self.new = {s: "new-" + s for s in release.SERVICES}
        self.state = {"lastGood": {"images": self.good, "sourceSha": "old-sha",
                     "configFingerprint": "old-config", "verifiedAt": "old-time"}}
        self.live = copy.deepcopy(self.good)
        self.version = 1
        self.writes = []
        for s, ref in self.new.items():
            Path(f"reports/{s}-image.json").write_text(json.dumps({"image": ref}))
        for name, effect in [("readstate", self.read), ("kubectl", self.kubectl),
                             ("imageslive", lambda: copy.deepcopy(self.live))]:
            p = patch.object(release, name, side_effect=effect)
            p.start()
            self.addCleanup(p.stop)

    def read(self):
        return {"metadata": {"resourceVersion": str(self.version)}}, copy.deepcopy(self.state)

    def kubectl(self, *args):
        # Exercise the real merge-patch writer and its optimistic concurrency field.
        self.assertEqual(args[:3], ("patch", "cm", "release-state"))
        body = json.loads(args[-1])
        if body["metadata"]["resourceVersion"] != str(self.version):
            raise RuntimeError("Conflict")
        self.state = json.loads(body["data"]["state.json"])
        self.writes.append(copy.deepcopy(self.state))
        self.version += 1
        return json.dumps({"metadata": {"resourceVersion": str(self.version)}})

    def deploy(self, images):
        self.live = copy.deepcopy(images)

    def test_needed_matrix(self):
        for recovery in (False, True):
            for files, changed in [("learning/README.md\nlearning/x.mmd\n", False),
                                   ("", False), ("src/orders/a.java\n", True),
                                   ("learning/scripts/ci.sh\n", True)]:
                with self.subTest(recovery=recovery, files=files):
                    self.state["recoveryFailed"] = recovery
                    with patch.object(release.subprocess, "check_output", return_value=files):
                        self.assertEqual(release.needed(), recovery or changed)

    def test_unknown_diff_or_missing_baseline_requires_build(self):
        with patch.object(release.subprocess, "check_output", side_effect=subprocess.CalledProcessError(1, "git")):
            self.assertTrue(release.needed())
        self.state = {}
        self.assertTrue(release.needed())

    def test_reconcile_pending_and_drift_matrix(self):
        for pending in (False, True):
            for drift in (False, True):
                with self.subTest(pending=pending, drift=drift):
                    self.state.pop("pending", None)
                    if pending:
                        self.state["pending"] = {"images": self.new}
                    self.live = copy.deepcopy(self.new if drift else self.good)
                    with patch.object(release, "preflight"), patch.object(release, "deploy", side_effect=self.deploy) as deploy, patch.object(release, "business_verify") as verify, patch.object(release, "evidence"):
                        release.reconcile()
                    self.assertEqual(deploy.call_count, int(pending or drift))
                    self.assertEqual(verify.call_count, int(pending or drift))
                    self.assertNotIn("pending", self.state)
                    self.assertEqual(self.live, self.good)

    def test_recovery_failure_strict_vs_repair(self):
        self.state["pending"] = {"images": self.new}
        with patch.object(release, "preflight"), patch.object(release, "deploy", side_effect=release.UnhealthyRelease("unhealthy")):
            with self.assertRaises(release.UnhealthyRelease):
                release.reconcile()
            self.assertNotIn("recoveryFailed", self.state)
            release.reconcile(allow_unhealthy=True)
        self.assertTrue(self.state["recoveryFailed"])
        self.assertIn("pending", self.state)
        self.assertTrue(release.needed())

    def test_infrastructure_error_never_bypassed(self):
        self.state["pending"] = {}
        self.live = self.new
        with patch.object(release, "preflight"), patch.object(release, "deploy", side_effect=RuntimeError("Forbidden")):
            with self.assertRaisesRegex(RuntimeError, "Forbidden"):
                release.reconcile(allow_unhealthy=True)
        self.assertEqual(self.writes, [])

    def test_http_disconnect_is_recoverable_business_failure(self):
        with patch.object(release, "verify", side_effect=http.client.RemoteDisconnected("no response")):
            with self.assertRaises(release.UnhealthyRelease):
                release.business_verify()

    def publishing(self):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch.object(release, "preflight", return_value="old-config"))
        stack.enter_context(patch.object(release, "reconcile"))
        stack.enter_context(patch.object(release, "checkimages"))
        stack.enter_context(patch.object(release.subprocess, "check_output", return_value="new-sha"))
        stack.enter_context(patch.object(release, "evidence"))
        return stack

    def test_deploy_and_verify_failure_restore_last_good(self):
        original = copy.deepcopy(self.state["lastGood"])
        for stage in ("deploy", "verify"):
            with self.subTest(stage=stage), self.publishing():
                calls = []

                def deploy(images):
                    calls.append(copy.deepcopy(images))
                    self.deploy(images)
                    if stage == "deploy" and len(calls) == 1:
                        raise release.UnhealthyRelease("rollout timeout")

                with patch.object(release, "deploy", side_effect=deploy), patch.object(release, "business_verify", side_effect=[release.UnhealthyRelease("smoke"), None] if stage == "verify" else [None]):
                    with self.assertRaises(release.UnhealthyRelease):
                        release.publish()
                self.assertEqual(calls, [self.new, self.good])
                self.assertEqual(self.live, self.good)
                self.assertEqual(self.state["lastGood"], original)
                self.assertNotIn("pending", self.state)

    def test_failed_rollback_retains_pending(self):
        with self.publishing(), patch.object(release, "deploy", side_effect=release.UnhealthyRelease("down")):
            with self.assertRaises(release.UnhealthyRelease):
                release.publish()
        self.assertEqual(self.state["pending"]["images"], self.new)
        self.assertEqual(self.state["lastGood"]["images"], self.good)

    def test_repair_candidate_records_recovery_history(self):
        self.state["recoveryFailed"] = True
        with self.publishing(), patch.object(release, "deploy", side_effect=self.deploy), patch.object(release, "business_verify"):
            release.publish()
        self.assertEqual(self.state["lastGood"]["images"], self.new)
        self.assertEqual(self.state["lastGood"]["sourceSha"], "new-sha")
        self.assertTrue(self.state["lastGood"]["recoveryFailed"])
        self.assertNotIn("recoveryFailed", self.state)
        self.assertNotIn("pending", self.state)

    def test_interruption_before_record_leaves_pending_for_next_reconcile(self):
        real_write = release.write
        writes = 0

        def fail_record(state, base):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("process interrupted before Record")
            return real_write(state, base)

        with self.publishing(), patch.object(release, "write", side_effect=fail_record), patch.object(release, "deploy", side_effect=self.deploy), patch.object(release, "business_verify"):
            with self.assertRaises(OSError):
                release.publish()
        self.assertIn("pending", self.state)
        self.assertEqual(self.live, self.new)
        with patch.object(release, "preflight"), patch.object(release, "deploy", side_effect=self.deploy), patch.object(release, "business_verify"), patch.object(release, "evidence"):
            release.reconcile()
        self.assertEqual(self.live, self.good)
        self.assertNotIn("pending", self.state)

    def test_after_record_reconcile_does_not_roll_back(self):
        with self.publishing(), patch.object(release, "deploy", side_effect=self.deploy), patch.object(release, "business_verify"):
            release.publish()
        with patch.object(release, "preflight"), patch.object(release, "deploy") as deploy:
            release.reconcile()
        deploy.assert_not_called()
        self.assertEqual(self.live, self.new)

    def test_write_rejects_stale_resource_version(self):
        base, state = self.read()
        self.version += 1
        with self.assertRaisesRegex(RuntimeError, "Conflict"):
            release.write(state, base)

    def test_adopt_changes_only_fingerprint(self):
        expected = copy.deepcopy(self.state)
        expected["lastGood"]["configFingerprint"] = "new-config"
        with patch.object(release, "preflight", return_value="new-config") as preflight, patch.object(release.subprocess, "run"), patch.object(release, "business_verify"), patch.object(release, "evidence"):
            release.adopt_config()
        self.assertEqual(self.state, expected)
        self.assertEqual(preflight.call_args_list, [unittest.mock.call(adopt=True)] * 2)

    def test_adopt_rejects_unsettled_state_and_image_drift(self):
        original = copy.deepcopy(self.state)
        for key in ("pending", "recoveryFailed", "drift", "missing"):
            self.state = copy.deepcopy(original)
            self.live = copy.deepcopy(self.good)
            if key == "drift": self.live = self.new
            elif key == "missing": self.state = {}
            else: self.state[key] = True
            with self.subTest(key=key), patch.object(release, "preflight"), patch.object(release, "business_verify") as verify:
                with self.assertRaises(AssertionError): release.adopt_config()
                verify.assert_not_called()
        self.assertEqual(self.writes, [])

    def test_adopt_failed_verify_or_concurrent_config_never_records(self):
        for failure in ("verify", "config", "images", "state"):
            self.live = copy.deepcopy(self.good)

            def verify():
                if failure == "verify": raise release.UnhealthyRelease("bad order")
                if failure == "images": self.live = self.new
                if failure == "state": self.version += 1

            with self.subTest(failure=failure), patch.object(release, "preflight", side_effect=["config", "changed" if failure == "config" else "config"]), patch.object(release.subprocess, "run"), patch.object(release, "business_verify", side_effect=verify), patch.object(release, "evidence"):
                with self.assertRaises((RuntimeError, AssertionError)):
                    release.adopt_config()
        self.assertEqual(self.writes, [])

    def test_adopt_requires_admin_context(self):
        with patch.object(release.subprocess, "check_output", return_value="retail-release"):
            with self.assertRaisesRegex(AssertionError, "context"):
                release.preflight(adopt=True)


if __name__ == "__main__":
    unittest.main()
