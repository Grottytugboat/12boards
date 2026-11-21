#!/usr/bin/env python3
"""Sonder project memory v1. Python standard library only; no model calls.

Semantic records are written by people/assistants. This utility validates them
and derives separately owned activity metadata from actual Git objects.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

VERSION = 1
MAX_FILE_BYTES = 131072
MAX_VILLAGE_BYTES = 524288
MAX_IDENTITY_BYTES = 18000
MAX_SYNC_BYTES = MAX_VILLAGE_BYTES + MAX_FILE_BYTES + 8192 + MAX_IDENTITY_BYTES + 256
CONATUS_ORIGIN = "https://sonder-conatus-tim.isthattimsullivan.chatgpt.site"
KNOWLEDGE_REPO = "Grottytugboat/sonder-knowledge"
KNOWLEDGE_REPO_ID = 1465982604
GENERATED_PATH = ".sonder/activity.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_CONATUS_ERRORS = frozenset({
    "Sign in with ChatGPT to open your project records.",
    "These project records belong to Tim.",
    "A GitHub workflow identity is required.",
    "Invalid workflow identity.",
    "Unsupported workflow signature.",
    "Expired or incorrectly addressed workflow identity.",
    "This workflow is not authorised to update the village.",
    "Invalid repository claims.",
    "Use the registered project memory workflow.",
    "GitHub identity verification is temporarily unavailable.",
    "GitHub returned no signing keys.",
    "Unknown workflow signing key.",
    "Invalid workflow signature.",
    "Repository identity does not match this project.",
    "This project and branch have not been registered.",
    "Invalid workflow sequence.",
    "The project mapping changed before this update was saved.",
    "Activity does not match this GitHub workflow.",
    "Invalid village briefing.",
    "Invalid or duplicate registry entry.",
    "Invalid village project seeds.",
    "A repository seed must match the registry.",
    "Duplicate village seed.",
    "Project update time is in the future.",
    "Send JSON.",
    "This update is too large.",
    "A JSON body is required.",
    "Invalid JSON.",
    "Shared storage is not ready yet. Your device notes are still safe.",
})


class MemoryError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise MemoryError(message)


def inside(root, relative):
    """Only fixed, relative repo paths; reject symlinks at every component."""
    rel = Path(relative)
    require(not rel.is_absolute() and ".." not in rel.parts, "Unsafe repository path")
    target = root
    for part in rel.parts:
        target = target / part
        require(not target.is_symlink(), f"Symlink is not allowed: {relative}")
    require(target.resolve().is_relative_to(root.resolve()), "Path leaves repository")
    return target


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_json(text):
    try:
        return json.loads(text, object_pairs_hook=unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              MemoryError(f"Non-finite JSON value: {value}")))
    except (json.JSONDecodeError, RecursionError) as exc:
        raise MemoryError("Invalid or excessively nested JSON") from exc


def read_json(path, limit=MAX_FILE_BYTES):
    require(path.is_file(), f"Missing file: {path.name}")
    require(path.stat().st_size <= limit, f"File exceeds {limit} bytes: {path.name}")
    return decode_json(path.read_text(encoding="utf-8"))


def utc_timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def https_url(value):
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not (
            parsed.username or parsed.password or any(ord(c) < 32 for c in value))
    except (ValueError, TypeError):
        return False


def schema_check(value, schema, document=None, path="$", depth=0):
    """Validate the JSON Schema subset used by the bundled v1 schemas.

    No dependency install or network schema fetch. This is not a general-purpose
    implementation of every JSON Schema keyword.
    """
    require(depth <= 30, f"{path}: nesting limit exceeded")
    document = document or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        require(ref.startswith("#/$defs/"), "Only local schema definitions are supported")
        return schema_check(value, document["$defs"][ref.split("/")[-1]], document, path, depth + 1)
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    matches = {"null": value is None, "boolean": type(value) is bool,
               "integer": type(value) is int, "string": isinstance(value, str),
               "array": isinstance(value, list), "object": isinstance(value, dict)}
    require(not types or any(matches.get(t, False) for t in types), f"{path}: wrong type")
    if "const" in schema:
        require(type(value) is type(schema["const"]) and value == schema["const"], f"{path}: unsupported value/version")
    if "enum" in schema:
        require(value in schema["enum"], f"{path}: unsupported value")
    if value is None:
        return
    if isinstance(value, str):
        require(len(value) >= schema.get("minLength", 0), f"{path}: value is empty")
        require(len(value) <= schema.get("maxLength", 1000000), f"{path}: value is too long")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, f"{path}: invalid format")
        if schema.get("format") == "date-time":
            require(utc_timestamp(value), f"{path}: use YYYY-MM-DDTHH:MM:SSZ")
        if schema.get("format") == "uri":
            require(https_url(value), f"{path}: use an HTTPS link without credentials")
    elif type(value) is int:
        require(schema.get("minimum", value) <= value <= schema.get("maximum", value), f"{path}: number out of range")
    elif isinstance(value, list):
        require(schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 1000000), f"{path}: wrong number of items")
        for index, item in enumerate(value):
            schema_check(item, schema.get("items", {}), document, f"{path}[{index}]", depth + 1)
    elif isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            require(key in value, f"{path}: missing {key}")
        if schema.get("additionalProperties") is False:
            require(not set(value) - set(properties), f"{path}: unknown fields {sorted(set(value) - set(properties))}")
        for key, item in value.items():
            if key in properties:
                schema_check(item, properties[key], document, f"{path}.{key}", depth + 1)


def validate_project(project, schema, allow_unmapped=False):
    if allow_unmapped:
        schema = deepcopy(schema)
        schema["properties"]["repository"]["type"] = ["string", "null"]
        schema["$defs"]["evidence"]["properties"]["checkedAt"]["type"] = ["string", "null"]
    schema_check(project, schema)
    unmapped = allow_unmapped and project["repository"] is None
    if unmapped:
        require(project["status"] == "unknown" and all(project[key] is None for key in
                ("statusSummary", "nextAction", "needsTim", "needsTimReason", "readyForReview",
                 "reviewSummary", "updatedAt", "updatedBy")),
                "Unmapped village seeds may carry historical facts only, not current state")
    assessed = (project["status"] != "unknown" or project["facts"] or
                project["nextAction"] is not None or project["needsTim"] is not None or
                project["readyForReview"] is not None or project["statusSummary"] is not None)
    if assessed and not unmapped:
        require(project["updatedAt"] is not None and project["updatedBy"] is not None,
                "Assessed semantic state needs updatedAt and updatedBy")
    require((project["updatedAt"] is None) == (project["updatedBy"] is None),
            "updatedAt and updatedBy must be set together")
    factual_state = (project["status"] != "unknown" or project["needsTim"] is not None or
                     project["readyForReview"] is not None or
                     (project["nextAction"] or {}).get("kind") == "agreed")
    if factual_state:
        require(bool(project["evidence"]), "Assessed status/flags or an agreed action need evidence")
    if project["status"] != "unknown":
        require(bool(project["statusSummary"]), "Known status needs a scoped statusSummary")
    if project["needsTim"] is True:
        require(bool(project["needsTimReason"]), "needsTim=true needs the actual decision/question")
    if project["readyForReview"] is True:
        require(bool(project["reviewSummary"]), "readyForReview=true needs a reviewSummary")
    return project


def validate_village(root, village, project_schema):
    require(isinstance(village, dict) and type(village.get("schemaVersion")) is int and village.get("schemaVersion") == VERSION, "Invalid village schemaVersion")
    require(utc_timestamp(village.get("updatedAt")), "Village updatedAt must be UTC")
    require(set(village) <= {"schemaVersion", "updatedAt", "registry", "briefing", "projects"}, "Unknown village fields")
    registry = village.get("registry", [])
    require(isinstance(registry, list) and len(registry) <= 500, "Invalid village registry")
    repositories, numeric_ids = set(), set()
    for item in registry:
        require(isinstance(item, dict) and set(item) == {"projectId", "repository", "repositoryId", "defaultBranch"}, "Invalid registry entry")
        require(isinstance(item["projectId"], str) and PROJECT_ID.fullmatch(item["projectId"]), "Invalid registry projectId")
        require(isinstance(item["repository"], str) and REPOSITORY.fullmatch(item["repository"]), "Invalid registry repository")
        require(type(item["repositoryId"]) is int and item["repositoryId"] > 0, "Registry repositoryId must be a positive integer")
        require(isinstance(item["defaultBranch"], str) and 0 < len(item["defaultBranch"]) <= 255 and not any(ord(c) < 32 for c in item["defaultBranch"]), "Invalid default branch")
        require(item["repository"].lower() not in repositories and item["repositoryId"] not in numeric_ids, "Duplicate registry repository identity")
        repositories.add(item["repository"].lower()); numeric_ids.add(item["repositoryId"])
    briefing = village.get("briefing", {})
    require(isinstance(briefing, dict), "Village briefing must be an object")
    if "sourceUrl" in briefing:
        require(https_url(briefing["sourceUrl"]), "Invalid briefing sourceUrl")
    if "checkedAt" in briefing:
        require(briefing["checkedAt"] is None or utc_timestamp(briefing["checkedAt"]), "Invalid briefing checkedAt")
    top = briefing.get("topThree", [])
    require(isinstance(top, list) and len(top) <= 3, "briefing.topThree allows at most three entries")
    for item in top:
        require(isinstance(item, dict) and set(item) == {"projectId", "title", "owner", "sourceUrl"}, "Invalid topThree item")
        require(isinstance(item["projectId"], str) and PROJECT_ID.fullmatch(item["projectId"]), "Invalid topThree projectId")
        require(isinstance(item["title"], str) and 0 < len(item["title"]) <= 500, "Invalid topThree title")
        require(item["owner"] is None or isinstance(item["owner"], str) and 0 < len(item["owner"]) <= 160, "Invalid topThree owner")
        require(https_url(item["sourceUrl"]), "Invalid topThree sourceUrl")
    projects = village.get("projects", [])
    require(isinstance(projects, list) and len(projects) <= 500, "Invalid village projects")
    seed_ids = set()
    for project in projects:
        validate_project(project, project_schema, allow_unmapped=True)
        identity = (project["projectId"], (project["repository"] or "").lower())
        require(identity not in seed_ids, "Duplicate village seed repository record")
        seed_ids.add(identity)


def validate(root):
    schema = read_json(inside(root, ".sonder/project.schema.json"))
    project = validate_project(read_json(inside(root, ".sonder/project.json")), schema)
    text = inside(root, "PROJECT.md").read_text(encoding="utf-8")
    require(text.count(f"<!-- sonder-project-id: {project['projectId']} -->") == 1,
            "PROJECT.md must contain exactly one matching project identity marker")
    require(len(text.encode()) <= MAX_FILE_BYTES, "PROJECT.md is too large")
    agents = inside(root, "AGENTS.md").read_text(encoding="utf-8")
    require(agents.count("<!-- sonder-project-memory:start -->") == 1 and
            agents.count("<!-- sonder-project-memory:end -->") == 1 and
            agents.index("<!-- sonder-project-memory:start -->") < agents.index("<!-- sonder-project-memory:end -->"),
            "AGENTS.md needs one complete managed project-memory section")
    activity = read_json(inside(root, GENERATED_PATH))
    schema_check(activity, read_json(inside(root, ".sonder/activity.schema.json")))
    require(activity["projectId"] == project["projectId"] and activity["repository"] == project["repository"], "Activity identity differs from project")
    nullable = [activity[k] is None for k in ("ref", "headSha", "headUrl", "committedAt", "subject", "recordedAt")]
    require(all(nullable) or not any(nullable), "Activity must be wholly unobserved or have complete commit metadata")
    if activity["headSha"]:
        require(activity["headUrl"] == f"https://github.com/{project['repository']}/commit/{activity['headSha']}", "Activity commit URL does not match identity")
        require(activity["recordedAt"] == activity["committedAt"], "recordedAt is deterministic source commit time")
    settings = read_json(inside(root, ".sonder/automation.json"))
    require(isinstance(settings, dict) and set(settings) == {"schemaVersion", "commitActivity", "syncToConatus"} and type(settings["schemaVersion"]) is int and settings["schemaVersion"] == VERSION and type(settings["commitActivity"]) is bool and type(settings["syncToConatus"]) is bool, "Invalid automation.json")
    village_path = inside(root, ".sonder/village.json")
    if village_path.exists():
        require(project["repository"] == KNOWLEDGE_REPO, "Village publication is restricted to the knowledge repository")
        validate_village(root, read_json(village_path, MAX_VILLAGE_BYTES), schema)
    return project, settings


def git(root, *args, check=True):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if check:
        require(result.returncode == 0, f"Git operation failed: {args[0]}")
    return result


def push_context(root, project, event_path, fetch_base=False):
    event = read_json(Path(event_path), 10 * 1024 * 1024)
    require(event.get("deleted") is not True, "Deleted refs cannot publish project memory")
    repo = event.get("repository", {})
    require(repo.get("full_name") == project["repository"], "Event repository does not match project record")
    ref = event.get("ref") or os.environ.get("GITHUB_REF", "")
    require(ref == "refs/heads/" + repo.get("default_branch", ""), "Only the default branch can publish activity")
    require(git(root, "check-ref-format", ref, check=False).returncode == 0, "Invalid branch ref")
    sha = event.get("after") or os.environ.get("GITHUB_SHA", "")
    require(isinstance(sha, str) and SHA.fullmatch(sha), "Invalid source commit SHA")
    require(git(root, "rev-parse", "HEAD").stdout.decode().strip() == sha, "Checkout must exactly match the event commit")
    if os.environ.get("GITHUB_SHA"):
        require(os.environ["GITHUB_SHA"] == sha, "Event SHA differs from workflow SHA")
    before = event.get("before")
    if before is not None:
        require(isinstance(before, str) and SHA.fullmatch(before), "Invalid before SHA")
    if before and before != "0" * 40:
        if git(root, "cat-file", "-e", before + "^{commit}", check=False).returncode != 0 and fetch_base:
            git(root, "fetch", "--no-tags", "--depth=1", "origin", before)
        require(git(root, "cat-file", "-e", before + "^{commit}", check=False).returncode == 0,
                "Push base is unavailable; fetch it or use --fetch-base")
        raw = git(root, "diff", "--name-only", "-z", before, sha, "--").stdout
    elif before == "0" * 40:
        raw = git(root, "ls-tree", "-r", "--name-only", "-z", sha).stdout
    else:
        # A manual dispatch has no push range. Compare with the first parent,
        # including merge commits (diff-tree without -m reports no merge files).
        parent = git(root, "rev-parse", "--verify", sha + "^", check=False)
        if parent.returncode == 0:
            raw = git(root, "diff", "--name-only", "-z", parent.stdout.decode().strip(), sha, "--").stdout
        else:
            raw = git(root, "ls-tree", "-r", "--name-only", "-z", sha).stdout
    paths = [p.decode("utf-8", errors="replace") for p in raw.split(b"\0") if p]
    stamp = git(root, "show", "-s", "--format=%cI", sha).stdout.decode().strip()
    committed = datetime.fromisoformat(stamp).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    subject = git(root, "show", "-s", "--format=%s", sha).stdout.decode("utf-8", errors="replace").strip()[:300]
    actor = event.get("sender", {}).get("login") or os.environ.get("GITHUB_ACTOR")
    activity = {"schemaVersion": VERSION, "projectId": project["projectId"],
                "repository": project["repository"], "ref": ref, "headSha": sha,
                "headUrl": f"https://github.com/{project['repository']}/commit/{sha}",
                "committedAt": committed, "subject": subject, "actor": actor,
                "changedFiles": len(paths), "recordedAt": committed}
    schema_check(activity, read_json(inside(root, ".sonder/activity.schema.json")))
    return event, activity, paths


def substantive(path):
    # Classification controls activity-file churn, not whether docs are useful.
    # All non-generated pushes can still sync semantic records to Conatus.
    lower = path.lower()
    return not (path in {"PROJECT.md", "AGENTS.md", GENERATED_PATH} or
                lower.startswith(("docs/", "decisions/", "agents/", "integrations/", "templates/")) or
                lower.endswith((".md", ".mdx", ".rst")) or
                path in {".sonder/project.json", ".sonder/village.json"})


def write_json_atomic(path, value):
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as handle:
        temp = Path(handle.name)
        handle.write(text)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return True


def update_activity(root, event_path, fetch_base=False):
    project, settings = validate(root)
    _, activity, paths = push_context(root, project, event_path, fetch_base)
    if not settings["commitActivity"]:
        return "Activity commits disabled; semantic records unchanged."
    if not any(substantive(path) for path in paths):
        return "Documentation/record-only push: no activity commit needed."
    changed = write_json_atomic(inside(root, GENERATED_PATH), activity)
    return "Activity metadata updated; semantic records unchanged." if changed else "Activity already current."


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MemoryError("Authentication request redirect refused")


def request_json(request, limit, stage="Remote request"):
    try:
        with build_opener(NoRedirect).open(request, timeout=25) as response:
            raw = response.read(limit + 1)
    except HTTPError as exc:
        detail = ""
        if stage == "Conatus sync":
            try:
                error_bytes = exc.read(8193)
                error = decode_json(error_bytes.decode("utf-8")) if len(error_bytes) <= 8192 else None
                message = error.get("message") if isinstance(error, dict) else None
                if isinstance(message, str) and message in SAFE_CONATUS_ERRORS:
                    detail = ": " + message
            except (OSError, UnicodeDecodeError, MemoryError):
                pass
        # Only locally allowlisted literal messages can leave the response body.
        raise MemoryError(f"{stage} failed (HTTP {exc.code}){detail}") from None
    except MemoryError:
        raise MemoryError(f"{stage}: authentication redirect refused") from None
    except (URLError, TimeoutError, OSError):
        raise MemoryError(f"{stage} failed; check endpoint availability and job permissions") from None
    require(len(raw) <= limit, f"{stage} response exceeded size limit")
    try:
        return decode_json(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, MemoryError):
        raise MemoryError(f"{stage} returned invalid JSON") from None


def sync_conatus(root, event_path, fetch_base=False):
    project, settings = validate(root)
    if not settings["syncToConatus"]:
        return "Conatus sync is disabled; no credentials requested or data sent."
    require(os.environ.get("GITHUB_ACTIONS") == "true", "OIDC sync runs only in GitHub Actions")
    require(os.environ.get("GITHUB_EVENT_NAME") in {"push", "workflow_dispatch", "schedule"}, "This event cannot sync records")
    event, activity, paths = push_context(root, project, event_path, fetch_base)
    if os.environ.get("GITHUB_EVENT_NAME") == "push" and paths and all(p == GENERATED_PATH for p in paths):
        return "Generated activity-only push: sync skipped."
    payload = {"project": project, "activity": activity}
    village_path = inside(root, ".sonder/village.json")
    if village_path.exists():
        require(event["repository"].get("id") == KNOWLEDGE_REPO_ID and
                event["repository"].get("full_name") == KNOWLEDGE_REPO,
                "Only the allowlisted knowledge repository can publish village data")
        payload["village"] = read_json(village_path, MAX_VILLAGE_BYTES)
    request_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    require(request_url and request_token, "Missing GitHub OIDC environment; job needs id-token: write")
    url = urlsplit(request_url)
    require(url.scheme == "https" and (url.hostname or "").endswith(".actions.githubusercontent.com") and not url.username and not url.password, "Unexpected OIDC request origin")
    query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k != "audience"]
    query.append(("audience", CONATUS_ORIGIN))
    request_url = urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), ""))
    token_result = request_json(Request(request_url, headers={"Authorization": "Bearer " + request_token}), 65536,
                                stage="GitHub identity request")
    token = token_result.get("value") if isinstance(token_result, dict) else None
    require(isinstance(token, str) and 0 < len(token) <= MAX_IDENTITY_BYTES and token.isascii() and
            not any(c.isspace() for c in token), "OIDC response did not contain a valid bounded token")
    # Keep the short-lived proof in the HTTPS JSON envelope. The Sites gateway
    # reserves Authorization for its own auth; the Worker verifies this proof.
    # It is never part of project/activity/village records or a saved JSON file.
    payload["workflowIdentity"] = token
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    require(len(body) <= MAX_SYNC_BYTES, "Sync payload exceeds limit")
    response = request_json(Request(CONATUS_ORIGIN + "/api/project-sync", data=body, method="POST",
                                   headers={"Content-Type": "application/json"}), 65536, stage="Conatus sync")
    require(isinstance(response, dict) and response.get("ok") is True, "Conatus did not acknowledge the sync")
    return f"Conatus acknowledged project {project['projectId']} at {activity['headSha'][:12]}."


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "activity", "sync"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--fetch-base", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "validate":
            project, _ = validate(root)
            print(f"Project memory v1 valid: {project['projectId']}")
        else:
            require(args.event, "An event JSON path is required")
            function = update_activity if args.command == "activity" else sync_conatus
            print(function(root, args.event, args.fetch_base))
        return 0
    except (MemoryError, OSError, UnicodeDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Project memory error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
