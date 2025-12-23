"""
Stack Overflow API Module - Fetch Q&A data for friction analysis prototype.
"""

import requests
import time
import re
from datetime import datetime
from typing import Iterator, Optional, List, Dict
import logging
from html import unescape

logger = logging.getLogger(__name__)

SO_API_BASE = "https://api.stackexchange.com/2.3"


class StackOverflowAPI:
    """Interface to Stack Exchange API for fetching Q&A data."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize API client.

        Args:
            api_key: Optional Stack Exchange API key for higher rate limits
        """
        self.api_key = api_key
        self.request_count = 0
        self.last_request_time = 0
        self.quota_remaining = 300

    def get_top_users(self, tag: str, page: int = 1, pagesize: int = 10) -> Dict:
        """Get top users for a specific tag."""
        params = {
            "page": page,
            "pagesize": pagesize,
            "order": "desc",
            "sort": "reputation",
        }
        return self._make_request(f"tags/{tag}/top-answerers/all_time", params)

    def get_user_info(self, user_id: int) -> Dict:
        """Get user profile information."""
        params = {}
        return self._make_request(f"users/{user_id}", params)

    def get_user_answers(
        self,
        user_id: int,
        page: int = 1,
        pagesize: int = 100,
        fromdate: Optional[int] = None,
        todate: Optional[int] = None,
    ) -> Dict:
        """
        Get answers by a specific user.

        Returns answers with question data for response time calculation.
        """
        params = {
            "page": page,
            "pagesize": pagesize,
            "order": "asc",  # Chronological order
            "sort": "creation",
            "filter": "withbody",  # Include body
        }
        if fromdate:
            params["fromdate"] = fromdate
        if todate:
            params["todate"] = todate
        return self._make_request(f"users/{user_id}/answers", params)

    def get_user_tags(self, user_id: int, page: int = 1, pagesize: int = 100) -> Dict:
        """Get tags a user has answered in."""
        params = {
            "page": page,
            "pagesize": pagesize,
            "order": "desc",
            "sort": "popular",
        }
        return self._make_request(f"users/{user_id}/tags", params)

    def get_user_top_tags(self, user_id: int) -> Dict:
        """Get user's top tags with answer stats."""
        params = {
            "pagesize": 50,
        }
        return self._make_request(f"users/{user_id}/top-answer-tags", params)

    def get_questions_by_ids(self, question_ids: list) -> Dict:
        """Get questions by IDs (to get tags)."""
        if not question_ids:
            return {"items": []}
        ids = ";".join(str(qid) for qid in question_ids[:100])
        params = {"filter": "withbody"}
        return self._make_request(f"questions/{ids}", params)

    def _rate_limit(self):
        """Respect Stack Exchange rate limits (30 requests/second max)."""
        min_interval = 0.1  # 100ms between requests
        elapsed = time.time() - self.last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
        self.request_count += 1

    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make API request with error handling."""
        self._rate_limit()

        params["site"] = "stackoverflow"
        if self.api_key:
            params["key"] = self.api_key

        url = f"{SO_API_BASE}/{endpoint}"

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            self.quota_remaining = data.get("quota_remaining", 0)
            if self.quota_remaining < 10:
                logger.warning(f"API quota low: {self.quota_remaining} remaining")

            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def get_questions_with_answers(
        self,
        tag: str,
        page: int = 1,
        pagesize: int = 100,
        fromdate: Optional[int] = None,
        todate: Optional[int] = None,
    ) -> Dict:
        """
        Fetch questions with their answers for a specific tag.

        Args:
            tag: Tag to filter questions
            page: Page number
            pagesize: Results per page (max 100)
            fromdate: Unix timestamp for start date
            todate: Unix timestamp for end date

        Returns:
            API response with questions
        """
        params = {
            "tagged": tag,
            "page": page,
            "pagesize": pagesize,
            "order": "desc",
            "sort": "creation",
            "filter": "withbody",  # Include body
        }

        if fromdate:
            params["fromdate"] = fromdate
        if todate:
            params["todate"] = todate

        logger.info(f"Fetching questions page {page} for tag: {tag}")
        return self._make_request("questions", params)

    def get_answers_for_questions(
        self,
        question_ids: List[int],
    ) -> Dict:
        """
        Fetch answers for specific questions.

        Args:
            question_ids: List of question IDs

        Returns:
            API response with answers
        """
        if not question_ids:
            return {"items": []}

        ids = ";".join(str(qid) for qid in question_ids[:100])

        params = {
            "order": "desc",
            "sort": "creation",
            "filter": "!nNPvSNdWme",  # Include body
        }

        logger.info(f"Fetching answers for {len(question_ids)} questions")
        return self._make_request(f"questions/{ids}/answers", params)


def extract_code_blocks(html_body: str) -> tuple:
    """
    Extract code blocks from HTML body.

    Returns:
        (code_block_count, total_code_length)
    """
    code_pattern = r"<code>(.*?)</code>"
    blocks = re.findall(code_pattern, html_body, re.DOTALL)
    total_length = sum(len(unescape(block)) for block in blocks)
    return len(blocks), total_length


def strip_html(html_body: str) -> str:
    """Strip HTML tags from body."""
    clean = re.sub(r"<[^>]+>", "", html_body)
    return unescape(clean)


def detect_conceptual_question(title: str, body: str) -> bool:
    """Detect if question asks 'why' or 'how does X work'."""
    conceptual_patterns = [
        r"\bwhy\b",
        r"\bhow does\b",
        r"\bwhat is the difference\b",
        r"\bexplain\b",
        r"\bunderstand\b",
        r"\bunder the hood\b",
        r"\bbest practice\b",
    ]
    text = (title + " " + body).lower()
    return any(re.search(p, text) for p in conceptual_patterns)


def calculate_question_complexity(
    body_length: int,
    code_block_count: int,
    code_length: int,
    tag_count: int,
    is_conceptual: bool,
) -> float:
    """
    Estimate question complexity from observable features.

    Returns: 0.0 (simple) to 1.0 (complex)
    """
    factors = []

    # Length factors
    body_length_norm = min(body_length / 2000, 1.0)
    factors.append(body_length_norm * 0.20)

    # Code complexity
    code_length_norm = min(code_length / 500, 1.0)
    factors.append(code_length_norm * 0.25)

    # Multiple code blocks suggest multi-step problem
    code_blocks_norm = min(code_block_count / 3, 1.0)
    factors.append(code_blocks_norm * 0.15)

    # Tag count (more tags = more concepts)
    tag_count_norm = min(tag_count / 5, 1.0)
    factors.append(tag_count_norm * 0.15)

    # Conceptual question (harder)
    factors.append(0.25 if is_conceptual else 0.0)

    return min(sum(factors), 1.0)


def parse_question(item: Dict) -> Optional[Dict]:
    """Parse a question from API response."""
    try:
        body = item.get("body", "")
        title = item.get("title", "")
        tags = item.get("tags", [])

        body_text = strip_html(body)
        code_blocks, code_length = extract_code_blocks(body)
        is_conceptual = detect_conceptual_question(title, body_text)

        complexity = calculate_question_complexity(
            len(body_text),
            code_blocks,
            code_length,
            len(tags),
            is_conceptual,
        )

        return {
            "question_id": item["question_id"],
            "creation_date": datetime.fromtimestamp(item["creation_date"]),
            "title": title,
            "body_length": len(body_text),
            "code_block_count": code_blocks,
            "code_length": code_length,
            "tags": tags,
            "tag_count": len(tags),
            "score": item.get("score", 0),
            "view_count": item.get("view_count", 0),
            "answer_count": item.get("answer_count", 0),
            "accepted_answer_id": item.get("accepted_answer_id"),
            "owner_user_id": item.get("owner", {}).get("user_id"),
            "owner_reputation": item.get("owner", {}).get("reputation", 0),
            "is_conceptual": is_conceptual,
            "complexity_score": complexity,
        }
    except Exception as e:
        logger.warning(f"Failed to parse question: {e}")
        return None


def parse_answer(item: Dict, question: Dict) -> Optional[Dict]:
    """Parse an answer from API response."""
    try:
        body = item.get("body", "")
        body_text = strip_html(body)
        code_blocks, code_length = extract_code_blocks(body)

        answer_date = datetime.fromtimestamp(item["creation_date"])
        question_date = question["creation_date"]
        response_time = (answer_date - question_date).total_seconds()

        return {
            "answer_id": item["answer_id"],
            "question_id": item["question_id"],
            "creation_date": answer_date,
            "body_length": len(body_text),
            "code_length": code_length,
            "score": item.get("score", 0),
            "is_accepted": item.get("is_accepted", False),
            "owner_user_id": item.get("owner", {}).get("user_id"),
            "owner_reputation": item.get("owner", {}).get("reputation", 0),
            "response_time_seconds": response_time,
            # Copy question data
            "question_complexity": question["complexity_score"],
            "question_tags": question["tags"],
            "question_owner_reputation": question["owner_reputation"],
        }
    except Exception as e:
        logger.warning(f"Failed to parse answer: {e}")
        return None
