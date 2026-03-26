"""Live match preview API handler functions extracted from web_api."""

import re
from typing import Any, Callable

from flask import jsonify

from apps.core.logging_config import setup_logging

logger = setup_logging(__name__)


def test_match_live_response(
    *,
    payload: Any,
    get_streams: Callable[[], Any],
    get_m3u_accounts: Callable[[], Any],
    is_dangerous_regex: Callable[[str], bool],
):
    """Handle live stream matching preview with regex and TVG-ID priority."""
    try:
        data = payload
        if not data:
            return jsonify({"error": "Missing request body"}), 400

        channel_name = data.get("channel_name", "Unknown Channel")
        match_by_tvg_id = data.get("match_by_tvg_id", False)
        tvg_id = data.get("tvg_id", None)

        regex_patterns = data.get("regex_patterns", [])
        normalized_patterns = []
        for pattern in regex_patterns:
            if isinstance(pattern, dict):
                normalized_patterns.append(pattern)
            elif isinstance(pattern, str):
                normalized_patterns.append({"pattern": pattern, "priority": 0})

        match_priority_order = data.get("match_priority_order", ["tvg", "regex"])
        case_sensitive = data.get("case_sensitive", True)
        max_matches = data.get("max_matches", 100)

        all_streams = get_streams()
        if not all_streams:
            return jsonify({"matches": [], "total_streams": 0})

        m3u_accounts_list = get_m3u_accounts() or []
        m3u_account_map = {
            account.get("id"): account.get("name", f"Account {account.get('id')}")
            for account in m3u_accounts_list
            if account.get("id") is not None
        }

        whitespace_pattern = re.compile(r"(?<!\\) +")
        matches = []

        for stream in all_streams:
            if not isinstance(stream, dict):
                continue

            stream_name = stream.get("name", "")
            stream_id = stream.get("id")
            if not stream_name:
                continue

            stream_tvg_id = stream.get("tvg_id")
            stream_m3u_account = stream.get("m3u_account")

            matched = False
            priority = 0
            match_source = "regex"
            matched_pattern = None

            for match_type in match_priority_order:
                if match_type == "tvg":
                    if match_by_tvg_id and tvg_id and stream_tvg_id:
                        if stream_tvg_id == tvg_id:
                            matched = True
                            match_source = "tvg_id"
                            if match_priority_order[0] == "tvg":
                                priority = 1000
                            else:
                                priority = 0
                            break

                elif match_type == "regex":
                    if matched:
                        continue

                    search_name = stream_name if case_sensitive else stream_name.lower()
                    regex_matched = False
                    best_regex_priority = 0
                    best_pattern_str = None

                    for pattern_obj in normalized_patterns:
                        pattern = pattern_obj.get("pattern", "")
                        pattern_m3u_accounts = pattern_obj.get("m3u_accounts")
                        pattern_priority = pattern_obj.get("priority", 0)

                        if not pattern:
                            continue

                        if pattern_m3u_accounts and len(pattern_m3u_accounts) > 0:
                            if (
                                stream_m3u_account is None
                                or stream_m3u_account not in pattern_m3u_accounts
                            ):
                                continue

                        escaped_channel_name = re.escape(channel_name)
                        substituted_pattern = pattern.replace("CHANNEL_NAME", escaped_channel_name)

                        search_pattern = substituted_pattern if case_sensitive else substituted_pattern.lower()
                        search_pattern = whitespace_pattern.sub(r"\\s+", search_pattern)

                        try:
                            if is_dangerous_regex(search_pattern):
                                continue
                            if re.search(search_pattern, search_name):
                                regex_matched = True
                                if pattern_priority >= best_regex_priority:
                                    best_regex_priority = pattern_priority
                                    best_pattern_str = pattern
                        except re.error:
                            continue

                    if regex_matched:
                        matched = True
                        match_source = "regex"
                        priority = best_regex_priority
                        matched_pattern = best_pattern_str
                        break

            if matched:
                matches.append(
                    {
                        "stream_id": stream_id,
                        "stream_name": stream_name,
                        "stream_tvg_id": stream_tvg_id,
                        "m3u_account_name": m3u_account_map.get(stream_m3u_account),
                        "source": match_source,
                        "priority": priority,
                        "matched_pattern": matched_pattern,
                    }
                )

                if len(matches) >= max_matches:
                    break

        return jsonify(
            {
                "matches": matches,
                "total_tested_streams": len(all_streams),
                "total_matches": len(matches),
            }
        )
    except Exception as exc:
        logger.error(f"Error testing match live: {exc}")
        return jsonify({"error": "Internal Server Error"}), 500
