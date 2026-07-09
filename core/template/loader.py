"""Load the template rule set, transparently caching it on disk.

Resolution order:
    1. Fresh JSON cache on disk (within ``cache_ttl``) -> use it.
    2. Otherwise, fetch and parse the live Confluence template page.
    3. If that fails (network error, or no rules could be parsed), fall
       back to whatever is on disk even if stale, so the agent keeps
       working during a Confluence outage.
    4. If nothing is available at all, raise :class:`TemplateLoadError`.
"""

from __future__ import annotations

from clients.confluence_client import ConfluenceClient
from core.template.parser import parse_template_sections
from exceptions.api_errors import ConfluenceAPIError
from exceptions.validation_errors import TemplateLoadError
from models.section import TemplateRule
from parsers.html_parser import parse_sections
from utils.cache import JSONCache
from utils.logger import get_logger

logger = get_logger(__name__)


class TemplateLoader:
    """Loads and caches the :class:`TemplateRule` list used for validation."""

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        template_page_id: str,
        cache_file: str,
        cache_ttl: int,
    ) -> None:
        """Initialize the loader.

        Args:
            confluence_client: Client used to fetch the live template page.
            template_page_id: Confluence content id of the template page.
            cache_file: Path to the JSON cache file.
            cache_ttl: Freshness window for the cache, in seconds.
        """
        self._client = confluence_client
        self._page_id = template_page_id
        self._cache = JSONCache(cache_file, cache_ttl)

    def load(self) -> list[TemplateRule]:
        """Return the current template rule set, refreshing the cache if stale.

        Returns:
            List of :class:`TemplateRule` describing the mandatory/optional
            document structure.

        Raises:
            TemplateLoadError: If no cached rules exist and the live
                template page cannot be fetched or parsed.
        """
        if self._cache.is_fresh():
            logger.info("Using cached template rules (fresh).")
            cached = self._cache.load()
            if cached:
                return [TemplateRule.from_dict(r) for r in cached]

        try:
            rules = self._fetch_and_parse()
            if rules:
                self._cache.save([r.to_dict() for r in rules])
                logger.info("Refreshed template rules from Confluence (%d rules).", len(rules))
                return rules
            logger.warning("Live template page yielded no rules; falling back to cache.")
        except ConfluenceAPIError as exc:
            logger.warning("Could not refresh template from Confluence: %s", exc)

        stale = self._cache.load()
        if stale:
            logger.info("Using stale cached template rules as fallback.")
            return [TemplateRule.from_dict(r) for r in stale]

        raise TemplateLoadError(
            "No template rules available: Confluence fetch failed and no cache exists."
        )

    def _fetch_and_parse(self) -> list[TemplateRule]:
        page = self._client.get_page(self._page_id)
        sections = parse_sections(page.raw_html)
        return parse_template_sections(sections)
