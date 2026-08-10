"""Service to build and maintain allowed_product_issue_map from complaints data."""
from __future__ import annotations

import logging
from typing import Dict, List

from sqlalchemy import text

logger = logging.getLogger(__name__)


class ProductIssueService:
    """Manages the allowed_product_issue_map derived table."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def refresh_allowed_product_issue_map(self) -> None:
        """Refresh the allowed_product_issue_map table from complaints.

        Called after complaints ingestion completes.
        Generates all unique (product, issue) combinations from complaints table.
        """
        with self.session_factory.begin() as session:
            session.execute(text("DELETE FROM allowed_product_issue_map"))
            session.execute(
                text(
                    """
                    INSERT INTO allowed_product_issue_map (product, issue, complaint_count)
                    SELECT
                        c.product,
                        c.issue,
                        COUNT(*) as complaint_count
                    FROM complaints c
                    WHERE c.product IS NOT NULL AND c.issue IS NOT NULL
                    GROUP BY c.product, c.issue
                    """
                )
            )
            logger.info(
                "allowed_product_issue_map refreshed",
                extra={"table": "allowed_product_issue_map"},
            )

    def get_allowed_product_issue_map(self) -> Dict[str, List[str]]:
        """Retrieve allowed_product_issue_map as a dictionary.

        Returns:
            Dict mapping product_type -> list of allowed issue_types
            Example: {
                "credit_card": ["interest_rate", "fees", "fraud"],
                "mortgage": ["rate_changes", "payment_issues"]
            }
        """
        try:
            with self.session_factory() as session:
                query = text(
                    """
                    SELECT product, issue FROM allowed_product_issue_map
                    ORDER BY product, issue
                    """
                )
                rows = session.execute(query).fetchall()
        except Exception:
            return {}

        # Build hierarchical map
        result: Dict[str, List[str]] = {}
        for product, issue in rows:
            if product not in result:
                result[product] = []
            result[product].append(issue)

        return result

    def is_valid_product_issue(self, product: str, issue: str) -> bool:
        """Check if (product, issue) pair is valid (exists in allowed_product_issue_map)."""
        with self.session_factory() as session:
            query = text(
                """
                SELECT COUNT(*) FROM allowed_product_issue_map
                WHERE product = :product AND issue = :issue
                """
            )
            result = session.execute(query, {"product": product, "issue": issue}).scalar()
        return result is not None and result > 0

    def get_issues_for_product(self, product: str) -> List[str]:
        """Get all valid issues for a given product."""
        with self.session_factory() as session:
            query = text(
                """
                SELECT issue FROM allowed_product_issue_map
                WHERE product = :product
                ORDER BY issue
                """
            )
            rows = session.execute(query, {"product": product}).fetchall()
        return [row[0] for row in rows]
